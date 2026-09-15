#!/usr/bin/env python3
"""
api_visualizer.py
------------------
Reads a Python file containing FastAPI route definitions (like the classic
`@app.get(...)` / `@app.post(...)` style) and produces a visual diagram
showing how your endpoints connect to your Pydantic models (request bodies
and response models).

No FastAPI import or code execution is needed -- the file is parsed
statically with Python's `ast` module, so it's safe to run on any file.

USAGE
-----
    python api_visualizer.py path/to/your_api.py
    python api_visualizer.py path/to/your_api.py --out my_diagram

OUTPUTS
-------
    <out>.png   A picture of the graph (endpoints + models + relationships)
    <out>.mmd   A Mermaid flowchart (paste into https://mermaid.live or
                render in any Markdown viewer/editor that supports Mermaid)
    Console     A readable route table

DEPENDENCIES
------------
    pip install networkx matplotlib
"""

import argparse
import ast
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")  # safe headless backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx

HTTP_METHODS = {"get", "post", "put", "delete", "patch", "options", "head"}

METHOD_COLORS = {
    "GET": "#4CAF50",
    "POST": "#FF9800",
    "PUT": "#2196F3",
    "DELETE": "#F44336",
    "PATCH": "#9C27B0",
    "OPTIONS": "#607D8B",
    "HEAD": "#607D8B",
}
MODEL_COLOR = "#90CAF9"


# --------------------------------------------------------------------------
# 1. Static analysis of the source file
# --------------------------------------------------------------------------
class FastAPIAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.models = {}      # model_name -> [(field_name, field_type), ...]
        self.endpoints = []   # list of dicts describing each route

    # --- Pydantic models -------------------------------------------------
    def visit_ClassDef(self, node):
        base_names = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                base_names.append(b.id)
            elif isinstance(b, ast.Attribute):
                base_names.append(b.attr)

        if "BaseModel" in base_names:
            fields = []
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    try:
                        type_str = ast.unparse(stmt.annotation)
                    except Exception:
                        type_str = "?"
                    fields.append((stmt.target.id, type_str))
            self.models[node.name] = fields

        self.generic_visit(node)

    # --- Route functions ---------------------------------------------------
    def visit_FunctionDef(self, node):
        self._handle_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self._handle_function(node)
        self.generic_visit(node)

    def _handle_function(self, node):
        for dec in node.decorator_list:
            route_info = self._parse_route_decorator(dec)
            if not route_info:
                continue
            method, path, response_model = route_info

            params = []
            for arg in node.args.args:
                if arg.arg == "self":
                    continue
                ann = ast.unparse(arg.annotation) if arg.annotation else None
                params.append((arg.arg, ann))

            self.endpoints.append(
                {
                    "method": method,
                    "path": path or "?",
                    "func": node.name,
                    "params": params,
                    "response_model": response_model,
                    "lineno": node.lineno,
                }
            )

    @staticmethod
    def _parse_route_decorator(dec):
        """Recognizes things like @app.get("/x"), @router.post("/y", response_model=Z)"""
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            method = dec.func.attr.lower()
            if method in HTTP_METHODS:
                path = None
                if dec.args and isinstance(dec.args[0], ast.Constant):
                    path = dec.args[0].value

                response_model = None
                for kw in dec.keywords:
                    if kw.arg == "response_model":
                        try:
                            response_model = ast.unparse(kw.value)
                        except Exception:
                            pass
                return method.upper(), path, response_model
        return None


def analyze_file(path):
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source, filename=path)
    analyzer = FastAPIAnalyzer()
    analyzer.visit(tree)
    # keep endpoints ordered by their line number (i.e. code order)
    analyzer.endpoints.sort(key=lambda e: e["lineno"])
    return analyzer


# --------------------------------------------------------------------------
# 2. Build a graph out of the analysis
# --------------------------------------------------------------------------
def build_graph(analyzer):
    G = nx.DiGraph()

    for name in analyzer.models:
        G.add_node(f"model:{name}", label=name, kind="model")

    for i, ep in enumerate(analyzer.endpoints):
        node_id = f"endpoint:{i}"
        extra_params = ", ".join(
            f"{n}:{t}" for n, t in ep["params"] if t not in analyzer.models
        )
        label = f"{ep['method']} {ep['path']}\n{ep['func']}()"
        if extra_params:
            label += f"\n({extra_params})"

        G.add_node(node_id, label=label, kind="endpoint", method=ep["method"])

        for pname, ptype in ep["params"]:
            if ptype in analyzer.models:
                G.add_edge(f"model:{ptype}", node_id, label="request body")

        if ep["response_model"] and ep["response_model"] in analyzer.models:
            G.add_edge(node_id, f"model:{ep['response_model']}", label="response")

    return G


# --------------------------------------------------------------------------
# 3. Draw the graph with matplotlib
# --------------------------------------------------------------------------
def draw_graph(G, out_png):
    if len(G.nodes) == 0:
        print("No routes or models found -- nothing to draw.")
        return

    pos = nx.spring_layout(G, k=1.4, seed=42)

    plt.figure(figsize=(12, 8))

    model_nodes = [n for n, d in G.nodes(data=True) if d.get("kind") == "model"]
    endpoint_nodes = [n for n, d in G.nodes(data=True) if d.get("kind") == "endpoint"]

    # models: light blue rectangles (squares)
    nx.draw_networkx_nodes(
        G, pos, nodelist=model_nodes, node_shape="s",
        node_color=MODEL_COLOR, node_size=3200, edgecolors="#1565C0", linewidths=1.5
    )

    # endpoints: colored circles by HTTP method
    for method, color in METHOD_COLORS.items():
        nodes = [n for n in endpoint_nodes if G.nodes[n].get("method") == method]
        if nodes:
            nx.draw_networkx_nodes(
                G, pos, nodelist=nodes, node_shape="o",
                node_color=color, node_size=3800, edgecolors="black", linewidths=1.2
            )

    nx.draw_networkx_edges(
        G, pos, arrowstyle="-|>", arrowsize=18, edge_color="#555555", width=1.4,
        connectionstyle="arc3,rad=0.08"
    )

    labels = {n: d["label"] for n, d in G.nodes(data=True)}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8)

    edge_labels = nx.get_edge_attributes(G, "label")
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=7, font_color="#333333")

    legend_handles = [mpatches.Patch(color=c, label=m) for m, c in METHOD_COLORS.items()
                       if any(G.nodes[n].get("method") == m for n in endpoint_nodes)]
    legend_handles.append(mpatches.Patch(color=MODEL_COLOR, label="Pydantic model"))
    plt.legend(handles=legend_handles, loc="upper left", fontsize=8, framealpha=0.9)

    plt.title("API Flow Diagram", fontsize=14)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(out_png, dpi=180)
    plt.close()
    print(f"Saved diagram -> {out_png}")


# --------------------------------------------------------------------------
# 4. Mermaid export (nice for pasting into docs / mermaid.live)
# --------------------------------------------------------------------------
def generate_mermaid(analyzer):
    lines = ["flowchart LR"]

    for name, fields in analyzer.models.items():
        field_str = "<br/>".join(f"{n}: {t}" for n, t in fields) or "&nbsp;"
        lines.append(f'    M_{name}["{name}<br/>{field_str}"]')

    for i, ep in enumerate(analyzer.endpoints):
        node_id = f"EP{i}"
        label = f"{ep['method']} {ep['path']}<br/>{ep['func']}()"
        lines.append(f'    {node_id}("{label}")')
        for pname, ptype in ep["params"]:
            if ptype in analyzer.models:
                lines.append(f"    M_{ptype} -->|body| {node_id}")
        if ep["response_model"] and ep["response_model"] in analyzer.models:
            lines.append(f"    {node_id} -->|response| M_{ep['response_model']}")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# 5. Console summary table
# --------------------------------------------------------------------------
def print_route_table(analyzer):
    print("\nDetected routes:")
    print("-" * 70)
    for ep in analyzer.endpoints:
        params = ", ".join(f"{n}: {t}" for n, t in ep["params"])
        print(f"  {ep['method']:<6} {ep['path']:<20} -> {ep['func']}({params})")
    print("-" * 70)
    if analyzer.models:
        print("\nDetected Pydantic models:")
        for name, fields in analyzer.models.items():
            field_str = ", ".join(f"{n}: {t}" for n, t in fields)
            print(f"  {name}({field_str})")
    print()


# --------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Visualize the flow of a FastAPI file.")
    parser.add_argument("source", help="Path to the .py file containing your FastAPI routes")
    parser.add_argument("--out", default="api_diagram", help="Output filename prefix (no extension)")
    args = parser.parse_args()

    analyzer = analyze_file(args.source)

    if not analyzer.endpoints:
        print("No @app.<method>(...) routes were found in this file.")
        sys.exit(1)

    print_route_table(analyzer)

    G = build_graph(analyzer)
    draw_graph(G, f"{args.out}.png")

    mermaid_text = generate_mermaid(analyzer)
    mmd_path = f"{args.out}.mmd"
    with open(mmd_path, "w", encoding="utf-8") as f:
        f.write(mermaid_text)
    print(f"Saved Mermaid flowchart -> {mmd_path} (paste it into https://mermaid.live to view/edit)")


if __name__ == "__main__":
    main()