# 🧠 ML RAG Full Course

A hands-on, end-to-end curriculum for mastering **Retrieval-Augmented Generation (RAG)** — from raw data ingestion to production-grade agentic pipelines with **LangGraph**. Every concept is paired with a runnable Jupyter notebook, so you build intuition by _doing_, not just reading.

---

## 📚 What You'll Learn

- How to ingest, chunk, and embed data for retrieval
- How to build, query, and enhance vector databases
- Advanced chunking strategies (semantic chunking, tables, images)
- Conversational memory techniques for multi-turn RAG
- Structured output generation from LLMs
- Human-in-the-loop workflows
- Building stateful agents and chains with LangGraph
- ReAct agents, tool use, and agent memory

---

## 🗂️ Repository Structure

```
ML_RAG_FULL_COURSE/
├── AGENTS/                              # Standalone agent design notebooks/resources
├── data/                                # Raw datasets used across notebooks
├── docs/                                # Reference documentation & notes
├── images/                              # Test Images
│
├── LANGGRAPH/                           # LangGraph-focused module
│   ├── chroma_db/                       # Local vector store for LangGraph examples
│   ├── output/                          # Generated outputs / run artifacts
│   ├── PDFS/                            # Source PDFs for LangGraph examples
│   ├── AGENT_WITH_MEMORY.ipynb          # Agents that retain conversational state
│   ├── basics.ipynb                     # LangGraph fundamentals
│   ├── CHAINS.ipynb                     # Building chains with LangGraph
│   ├── Chatbot_trial.ipynb              # End-to-end chatbot prototype
│   ├── graph.png                        # Example graph visualization
│   ├── REACT_AGENT.ipynb                # ReAct-style reasoning + acting agent
│   ├── Schema_DataClass.ipynb           # Typed state schemas for graphs
│   └── TOOLS.ipynb                      # Tool calling & tool binding
│
├── PDFS/                                # Shared PDF sources for core RAG notebooks
├── Query_ENHANCEMENT/                   # Query rewriting / expansion techniques
│
├── ADVANCE_CHUNKING_SEMANTIC.ipynb      # Semantic chunking strategies
├── Conversational_Memory_Techinques_RAG.ipynb  # Memory patterns for chat-based RAG
├── Directory_Loader.ipynb               # Bulk-loading documents from a directory
├── Embedding_Tables_Images.ipynb        # Embedding non-text content (tables/images)
├── Embedding_VectorDB.ipynb             # Core embedding + vector DB workflow
├── HumanINtheLoop_.ipynb                # Human-in-the-loop review/approval flows
├── Intro_to_data_injestion.ipynb        # Data ingestion fundamentals
├── Structured_OUTPUT.ipynb              # Enforcing structured LLM outputs
├── Renewable_Energy_Report.pdf          # Sample source document for RAG demos
├── test.ipynb                           # Scratch/testing notebook
├── test.txt                             # Scratch/testing text file
└── .gitignore
```

---

## 🧭 Suggested Learning Path

| Step | Notebook                                                                                                    | Focus                             |
| ---- | ----------------------------------------------------------------------------------------------------------- | --------------------------------- |
| 1    | `Intro_to_data_injestion.ipynb`                                                                             | Load & prepare raw data           |
| 2    | `Directory_Loader.ipynb`                                                                                    | Ingest documents at scale         |
| 3    | `ADVANCE_CHUNKING_SEMANTIC.ipynb`                                                                           | Chunk documents intelligently     |
| 4    | `Embedding_Tables_Images.ipynb`                                                                             | Embed multimodal content          |
| 5    | `Embedding_VectorDB.ipynb`                                                                                  | Store & query embeddings          |
| 6    | `Query_ENHANCEMENT/`                                                                                        | Improve retrieval quality         |
| 7    | `Conversational_Memory_Techinques_RAG.ipynb`                                                                | Add memory to RAG                 |
| 8    | `Structured_OUTPUT.ipynb`                                                                                   | Get reliable structured responses |
| 9    | `HumanINtheLoop_.ipynb`                                                                                     | Add review checkpoints            |
| 10   | `LANGGRAPH/basics.ipynb` → `CHAINS.ipynb` → `TOOLS.ipynb` → `REACT_AGENT.ipynb` → `AGENT_WITH_MEMORY.ipynb` | Build agentic workflows           |

---

## 🛠️ Tech Stack

- **LangChain** / **LangGraph** — orchestration & agent graphs
- **ChromaDB** — local vector storage
- **Jupyter Notebooks** — interactive learning
- **PDF/Directory loaders** — document ingestion

---
