/**
 * ==============================================================================
 * AI Food Recipe Generator - Client Script
 * ==============================================================================
 * Handles:
 * 1. Quick ingredient tag adding to input box
 * 2. Form submission loading indicators
 * 3. Save / Remove Favourite recipes via AJAX
 * 4. Interactive Chef AI Chatbot (with quick prompt chips)
 * 5. Clean Recipe Print functionality
 */

document.addEventListener("DOMContentLoaded", function () {
    // --------------------------------------------------------------------------
    // 1. Quick Ingredient Chips (Home Page)
    // --------------------------------------------------------------------------
    const ingredientInput = document.getElementById("ingredients-input");
    const quickChips = document.querySelectorAll(".chip-btn");

    quickChips.forEach(function (chip) {
        chip.addEventListener("click", function () {
            const ingredient = this.getAttribute("data-ingredient");
            if (!ingredientInput) return;

            let currentVal = ingredientInput.value.trim();
            if (!currentVal) {
                ingredientInput.value = ingredient;
            } else {
                // Check if ingredient is already present (case-insensitive)
                const items = currentVal.split(",").map(s => s.trim().toLowerCase());
                if (!items.includes(ingredient.toLowerCase())) {
                    ingredientInput.value = currentVal + ", " + ingredient;
                }
            }
            ingredientInput.focus();
        });
    });

    // --------------------------------------------------------------------------
    // 2. Generate Recipe Form Loading State
    // --------------------------------------------------------------------------
    const generateForm = document.getElementById("generate-recipe-form");
    const generateBtn = document.getElementById("generate-btn");

    if (generateForm && generateBtn) {
        generateForm.addEventListener("submit", function () {
            const inputVal = ingredientInput ? ingredientInput.value.trim() : "";
            if (inputVal) {
                generateBtn.disabled = true;
                generateBtn.innerHTML = "🍳 Cooking Up Your Recipes...";
                generateBtn.style.opacity = "0.85";
                generateBtn.style.cursor = "wait";
            }
        });
    }

    // --------------------------------------------------------------------------
    // 3. Save to Favourites via AJAX
    // --------------------------------------------------------------------------
    const saveFavButtons = document.querySelectorAll(".btn-save-fav");

    saveFavButtons.forEach(function (btn) {
        btn.addEventListener("click", function (e) {
            e.preventDefault();
            const recipeId = this.getAttribute("data-id");

            fetch("/api/favourites/add", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ recipe_id: recipeId })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    btn.innerHTML = "❤️ Saved to Favourites";
                    btn.classList.remove("btn-outline");
                    btn.classList.add("btn-accent");
                    btn.disabled = true;

                    // Update count in navigation if badge exists
                    const countBadge = document.getElementById("fav-count-badge");
                    if (countBadge) {
                        let currentCount = parseInt(countBadge.textContent) || 0;
                        countBadge.textContent = currentCount + 1;
                    }
                } else {
                    alert(data.message || "Could not save recipe.");
                }
            })
            .catch(err => {
                console.error("Error saving favourite:", err);
                alert("An error occurred while saving to favourites.");
            });
        });
    });

    // --------------------------------------------------------------------------
    // 4. Remove from Favourites (Favourites Page)
    // --------------------------------------------------------------------------
    const removeFavButtons = document.querySelectorAll(".btn-remove-fav");

    removeFavButtons.forEach(function (btn) {
        btn.addEventListener("click", function (e) {
            e.preventDefault();
            const favId = this.getAttribute("data-id");
            const card = document.getElementById("fav-card-" + favId);

            if (!confirm("Are you sure you want to remove this recipe from your favourites?")) {
                return;
            }

            fetch("/api/favourites/remove/" + favId, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    // Fade out and remove card from DOM
                    if (card) {
                        card.style.transition = "all 0.3s ease";
                        card.style.opacity = "0";
                        card.style.transform = "scale(0.9)";
                        setTimeout(() => {
                            card.remove();
                            // Check if no cards left
                            const remaining = document.querySelectorAll(".recipe-card");
                            if (remaining.length === 0) {
                                const container = document.getElementById("favourites-container");
                                if (container) {
                                    container.innerHTML = `
                                        <div class="generator-card" style="text-align: center; padding: 40px;">
                                            <p style="font-size: 1.1rem; color: var(--text-secondary); margin-bottom: 15px;">
                                                You have no saved favourite recipes yet.
                                            </p>
                                            <a href="/" class="btn btn-primary">🍲 Generate New Recipes</a>
                                        </div>
                                    `;
                                }
                            }
                        }, 300);
                    }

                    // Decrement navbar counter
                    const countBadge = document.getElementById("fav-count-badge");
                    if (countBadge) {
                        let currentCount = parseInt(countBadge.textContent) || 1;
                        countBadge.textContent = Math.max(0, currentCount - 1);
                    }
                } else {
                    alert(data.message || "Could not remove favourite.");
                }
            })
            .catch(err => {
                console.error("Error removing favourite:", err);
                alert("Error removing recipe.");
            });
        });
    });

    // --------------------------------------------------------------------------
    // 5. Print Recipe
    // --------------------------------------------------------------------------
    const printBtn = document.getElementById("btn-print-recipe");
    if (printBtn) {
        printBtn.addEventListener("click", function () {
            window.print();
        });
    }

    // --------------------------------------------------------------------------
    // 6. Interactive Chef AI Chatbot
    // --------------------------------------------------------------------------
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");
    const chatMessages = document.getElementById("chat-messages");
    const chatLangSelect = document.getElementById("chat-language");
    const chatChips = document.querySelectorAll(".chat-chip-btn");

    function appendMessage(sender, text) {
        if (!chatMessages) return;

        const row = document.createElement("div");
        row.className = sender === "user" ? "message-row user-row" : "message-row bot-row";

        const bubble = document.createElement("div");
        bubble.className = "message-bubble";

        // Convert newlines to breaks and simple bullets
        let formattedText = escapeHtml(text).replace(/\n/g, "<br>");
        bubble.innerHTML = formattedText;

        row.appendChild(bubble);
        chatMessages.appendChild(row);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function showTypingIndicator() {
        const row = document.createElement("div");
        row.className = "message-row bot-row typing-indicator-row";
        row.id = "typing-indicator";

        const bubble = document.createElement("div");
        bubble.className = "message-bubble";
        bubble.style.fontStyle = "italic";
        bubble.style.color = "var(--text-muted)";
        bubble.innerHTML = "👨‍🍳 Chef AI is preparing an answer...";

        row.appendChild(bubble);
        chatMessages.appendChild(row);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function removeTypingIndicator() {
        const indicator = document.getElementById("typing-indicator");
        if (indicator) {
            indicator.remove();
        }
    }

    function sendChatMessage(message) {
        if (!message || !message.trim()) return;

        appendMessage("user", message);
        showTypingIndicator();

        const lang = chatLangSelect ? chatLangSelect.value : "en";

        fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message,
                language: lang
            })
        })
        .then(res => res.json())
        .then(data => {
            removeTypingIndicator();
            if (data.reply) {
                appendMessage("bot", data.reply);
            } else if (data.message) {
                appendMessage("bot", data.message);
            } else {
                appendMessage("bot", "I could not generate an answer right now. Please try again.");
            }
        })
        .catch(err => {
            removeTypingIndicator();
            console.error("Chat error:", err);
            appendMessage("bot", "Network error communicating with Chef AI. Please verify your connection.");
        });
    }

    if (chatForm && chatInput) {
        chatForm.addEventListener("submit", function (e) {
            e.preventDefault();
            const message = chatInput.value.trim();
            if (message) {
                chatInput.value = "";
                sendChatMessage(message);
            }
        });
    }

    chatChips.forEach(function (chip) {
        chip.addEventListener("click", function () {
            const query = this.getAttribute("data-query");
            if (query) {
                sendChatMessage(query);
            }
        });
    });

    // Simple HTML escaping helper for chat security
    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }
});
