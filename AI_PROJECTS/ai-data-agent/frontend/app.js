// ==========================================
// CONFIG
// ==========================================

const API_BASE_URL = "http://127.0.0.1:8000";


// ==========================================
// STATE
// ==========================================

let currentConversationId = null;

let isSending = false;


// ==========================================
// DOM
// ==========================================

const chatMessages =
    document.getElementById("chatMessages");

const messageInput =
    document.getElementById("messageInput");

const sendBtn =
    document.getElementById("sendBtn");

const newChatBtn =
    document.getElementById("newChatBtn");

const conversationIdDisplay =
    document.getElementById("conversationIdDisplay");

const datasetInput =
    document.getElementById("datasetInput");

const datasetInfo =
    document.getElementById("datasetInfo");


// ==========================================
// INITIALIZATION
// ==========================================

async function initializeApp() {

    /*
    First check if this browser already
    has an active conversation.
    */

    const savedConversationId =
        localStorage.getItem("conversation_id");


    if (savedConversationId) {

        currentConversationId =
            savedConversationId;

        conversationIdDisplay.textContent =
            currentConversationId;

        console.log(
            "Restored conversation:",
            currentConversationId
        );

        await loadConversationMessages();

    }

    else {

        await createNewConversation();

    }

}


document.addEventListener(
    "DOMContentLoaded",
    initializeApp
);


// ==========================================
// CREATE NEW CONVERSATION
// ==========================================

async function createNewConversation() {

    try {

        const response =
            await fetch(
                `${API_BASE_URL}/api/conversations`,
                {
                    method: "POST"
                }
            );


        if (!response.ok) {

            throw new Error(
                "Failed to create conversation"
            );

        }


        const data =
            await response.json();


        /*
        IMPORTANT:

        This ID now belongs to this chat.

        Every future message will send
        this same ID.
        */

        currentConversationId =
            data.conversation_id;


        /*
        Save it in browser storage.

        So refreshing the page does NOT
        create a new conversation.
        */

        localStorage.setItem(
            "conversation_id",
            currentConversationId
        );


        conversationIdDisplay.textContent =
            currentConversationId;


        console.log(
            "New conversation:",
            currentConversationId
        );


        clearChatUI();

    }

    catch (error) {

        console.error(error);

        conversationIdDisplay.textContent =
            "Error creating chat";

    }

}


// ==========================================
// NEW CHAT BUTTON
// ==========================================

newChatBtn.addEventListener(
    "click",
    async () => {

        /*
        Remove current chat ID.

        Then create another one.
        */

        localStorage.removeItem(
            "conversation_id"
        );


        currentConversationId =
            null;


        await createNewConversation();

    }
);


// ==========================================
// SEND MESSAGE
// ==========================================

async function sendMessage() {

    const message =
        messageInput.value.trim();


    if (!message) return;

    if (isSending) return;


    /*
    Safety:

    If somehow no conversation exists,
    automatically create one.
    */

    if (!currentConversationId) {

        await createNewConversation();

    }


    isSending = true;

    sendBtn.disabled = true;


    // Add user message

    addMessage(
        "user",
        message
    );


    messageInput.value =
        "";


    autoResizeTextarea();


    // Add typing indicator

    const typingId =
        addTypingIndicator();


    try {

        /*
        Send the SAME conversation ID
        for every message in this chat.
        */

        const response =
            await fetch(
                `${API_BASE_URL}/api/chat`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({

                            message: message,

                            conversation_id:
                                currentConversationId

                        })
                }
            );


        if (!response.ok) {

            const errorData =
                await response.json();

            throw new Error(
                errorData.detail ||
                "Something went wrong"
            );

        }


        const data =
            await response.json();


        /*
        IMPORTANT:

        Always trust the conversation ID
        returned by backend.

        This protects us if the backend
        ever creates one automatically.
        */

        currentConversationId =
            data.conversation_id;


        localStorage.setItem(
            "conversation_id",
            currentConversationId
        );


        conversationIdDisplay.textContent =
            currentConversationId;


        removeTypingIndicator(
            typingId
        );


        /*
        Add assistant message.

        Chart is automatically passed here.
        */

        addMessage(
            "assistant",
            data.response,
            data
        );


    }

    catch (error) {

        console.error(error);


        removeTypingIndicator(
            typingId
        );


        addMessage(
            "assistant",
            `⚠️ Error: ${error.message}`
        );

    }

    finally {

        isSending = false;

        sendBtn.disabled = false;

        messageInput.focus();

    }

}


// ==========================================
// ADD MESSAGE
// ==========================================

function addMessage(
    role,
    content,
    extraData = null
) {

    removeWelcomeMessage();


    const row =
        document.createElement("div");


    row.classList.add(
        "message-row",
        role
    );


    const bubble =
        document.createElement("div");


    bubble.classList.add(
        "message-bubble"
    );


    bubble.textContent =
        content;


    row.appendChild(
        bubble
    );


    /*
    Automatically render chart.

    No chart_id needs to be manually
    pasted anywhere.
    */

    if (
        role === "assistant" &&
        extraData
    ) {

        let chartSource = null;


        /*
        BEST OPTION:

        Backend already provides
        base64 chart.
        */

        if (extraData.chart_base64) {

            chartSource =
                extraData.chart_base64;

        }


        /*
        FALLBACK:

        Use chart_url returned
        by backend.
        */

        else if (extraData.chart_url) {

            chartSource =
                `${API_BASE_URL}${extraData.chart_url}`;

        }


        if (chartSource) {

            const chartContainer =
                document.createElement("div");


            chartContainer.classList.add(
                "chart-container"
            );


            const chartImage =
                document.createElement("img");


            chartImage.src =
                chartSource;


            chartImage.alt =
                "Generated data visualization";


            chartImage.onerror =
                () => {

                    chartContainer.remove();

                    console.error(
                        "Failed to load chart"
                    );

                };


            chartContainer.appendChild(
                chartImage
            );


            bubble.appendChild(
                chartContainer
            );

        }

    }


    chatMessages.appendChild(
        row
    );


    scrollToBottom();

}


// ==========================================
// LOAD EXISTING CHAT
// ==========================================

async function loadConversationMessages() {

    if (!currentConversationId) return;


    try {

        const response =
            await fetch(
                `${API_BASE_URL}/api/conversations/${currentConversationId}/messages`
            );


        if (!response.ok) {

            /*
            Conversation may have been deleted
            from database.

            Create a fresh one.
            */

            localStorage.removeItem(
                "conversation_id"
            );


            currentConversationId =
                null;


            await createNewConversation();

            return;

        }


        const messages =
            await response.json();


        if (
            !messages ||
            messages.length === 0
        ) {

            return;

        }


        clearChatUI();


        for (
            const message of messages
        ) {

            addMessage(
                message.role,
                message.content
            );

        }

    }

    catch (error) {

        console.error(
            "Failed to load conversation:",
            error
        );

    }

}


// ==========================================
// TYPING INDICATOR
// ==========================================

function addTypingIndicator() {

    removeWelcomeMessage();


    const id =
        `typing-${Date.now()}`;


    const row =
        document.createElement("div");


    row.id =
        id;


    row.classList.add(
        "message-row",
        "assistant"
    );


    const bubble =
        document.createElement("div");


    bubble.classList.add(
        "message-bubble"
    );


    const typing =
        document.createElement("div");


    typing.classList.add(
        "typing"
    );


    for (
        let i = 0;
        i < 3;
        i++
    ) {

        const dot =
            document.createElement("span");


        typing.appendChild(
            dot
        );

    }


    bubble.appendChild(
        typing
    );


    row.appendChild(
        bubble
    );


    chatMessages.appendChild(
        row
    );


    scrollToBottom();


    return id;

}


function removeTypingIndicator(
    id
) {

    const element =
        document.getElementById(id);


    if (element) {

        element.remove();

    }

}


// ==========================================
// CLEAR CHAT
// ==========================================

function clearChatUI() {

    chatMessages.innerHTML =
        `
        <div class="welcome-message">

            <div class="welcome-icon">
                📊
            </div>

            <h2>
                Start analyzing your data
            </h2>

            <p>
                Upload a CSV file and ask questions about your dataset.
            </p>

            <div class="suggestions">

                <button
                    class="suggestion-btn"
                >
                    Give me an overview of this dataset
                </button>

                <button
                    class="suggestion-btn"
                >
                    What are the important insights?
                </button>

                <button
                    class="suggestion-btn"
                >
                    Create a visualization
                </button>

            </div>

        </div>
        `;


    attachSuggestionEvents();

}


function removeWelcomeMessage() {

    const welcome =
        document.querySelector(
            ".welcome-message"
        );


    if (welcome) {

        welcome.remove();

    }

}


// ==========================================
// SUGGESTIONS
// ==========================================

function attachSuggestionEvents() {

    const buttons =
        document.querySelectorAll(
            ".suggestion-btn"
        );


    buttons.forEach(
        (button) => {

            button.addEventListener(
                "click",
                () => {

                    messageInput.value =
                        button.textContent.trim();


                    sendMessage();

                }
            );

        }
    );

}


// ==========================================
// UPLOAD DATASET
// ==========================================

datasetInput.addEventListener(
    "change",
    async (event) => {

        const file =
            event.target.files[0];


        if (!file) return;


        const formData =
            new FormData();


        formData.append(
            "file",
            file
        );


        datasetInfo.textContent =
            "Uploading..."
        ;


        try {

            const response =
                await fetch(
                    `${API_BASE_URL}/api/datasets/upload`,
                    {
                        method: "POST",

                        body: formData
                    }
                );


            if (!response.ok) {

                const errorData =
                    await response.json();

                throw new Error(
                    errorData.detail ||
                    "Upload failed"
                );

            }


            const data =
                await response.json();


            datasetInfo.innerHTML =
                `
                <strong>
                    ${data.filename}
                </strong>

                <br>

                ${data.total_rows} rows

                <br>

                ${data.total_columns} columns
                `;


            addMessage(
                "assistant",
                `Dataset "${data.filename}" uploaded successfully. ` +
                `It contains ${data.total_rows} rows and ` +
                `${data.total_columns} columns.`
            );

        }

        catch (error) {

            console.error(error);

            datasetInfo.textContent =
                `Upload failed: ${error.message}`;

        }

    }
);


// ==========================================
// ENTER TO SEND
// ==========================================

messageInput.addEventListener(
    "keydown",
    (event) => {

        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            sendMessage();

        }

    }
);


// ==========================================
// SEND BUTTON
// ==========================================

sendBtn.addEventListener(
    "click",
    sendMessage
);


// ==========================================
// AUTO RESIZE
// ==========================================

messageInput.addEventListener(
    "input",
    autoResizeTextarea
);


function autoResizeTextarea() {

    messageInput.style.height =
        "auto";


    messageInput.style.height =
        `${messageInput.scrollHeight}px`;

}


// ==========================================
// SCROLL
// ==========================================

function scrollToBottom() {

    chatMessages.scrollTo({

        top:
            chatMessages.scrollHeight,

        behavior:
            "smooth"

    });

}


// Initial suggestion binding

attachSuggestionEvents();