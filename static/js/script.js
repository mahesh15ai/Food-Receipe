/**
 * ==============================================================================
 * AI Food Recipe Generator - Enhanced Client Script
 * ==============================================================================
 * Handles:
 * 1. Quick ingredient tag adding to input box with selected visual state
 * 2. Form submission loading indicators
 * 3. Save / Remove Favourite recipes via AJAX
 * 4. Interactive Chef AI Chatbot (with quick prompt chips)
 * 5. Clean Recipe Print functionality
 * 6. API Key Setup Modal
 */

document.addEventListener("DOMContentLoaded", function () {
    // --------------------------------------------------------------------------
    // 1. Quick Ingredient Chips (Home Page)
    // --------------------------------------------------------------------------
    const ingredientInput = document.getElementById("ingredients-input");
    const quickChips = document.querySelectorAll(".chip-btn:not(.chat-chip-btn)");

    // Restore pending ingredients saved before guest login
    const pendingIngredients = sessionStorage.getItem("pending_ingredients");
    if (pendingIngredients && ingredientInput && !ingredientInput.value) {
        ingredientInput.value = pendingIngredients;
        sessionStorage.removeItem("pending_ingredients");
    }

    const guestGenerateBtn = document.getElementById("guest-generate-btn");
    if (guestGenerateBtn && ingredientInput) {
        guestGenerateBtn.addEventListener("click", function () {
            if (ingredientInput.value.trim()) {
                sessionStorage.setItem("pending_ingredients", ingredientInput.value.trim());
            }
        });
    }

    function updateChipSelectionState() {
        if (!ingredientInput) return;
        const currentVal = ingredientInput.value.toLowerCase();
        const currentItems = currentVal.split(",").map(s => s.trim());

        quickChips.forEach(function (chip) {
            const ingredient = (chip.getAttribute("data-ingredient") || "").toLowerCase();
            if (ingredient && currentItems.includes(ingredient)) {
                chip.classList.add("selected");
            } else {
                chip.classList.remove("selected");
            }
        });
    }

    quickChips.forEach(function (chip) {
        chip.addEventListener("click", function () {
            const ingredient = this.getAttribute("data-ingredient");
            if (!ingredientInput) return;

            let currentVal = ingredientInput.value.trim();
            if (!currentVal) {
                ingredientInput.value = ingredient;
            } else {
                const items = currentVal.split(",").map(s => s.trim().toLowerCase());
                if (!items.includes(ingredient.toLowerCase())) {
                    ingredientInput.value = currentVal + ", " + ingredient;
                }
            }
            updateChipSelectionState();
            ingredientInput.focus();
        });
    });

    if (ingredientInput) {
        ingredientInput.addEventListener("input", updateChipSelectionState);
        updateChipSelectionState();
    }

    // --------------------------------------------------------------------------
    // 2. Generate Recipe Form Loading State
    // --------------------------------------------------------------------------
    const generateForm = document.getElementById("generate-recipe-form");
    const generateBtn = document.getElementById("generate-btn");

    if (generateForm && generateBtn) {
        generateForm.addEventListener("submit", function () {
            const inputVal = ingredientInput ? ingredientInput.value.trim() : "";
            if (inputVal) {
                generateBtn.style.pointerEvents = "none";
                generateBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Formulating Your Recipes...';
                generateBtn.style.opacity = "0.88";
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
                    btn.innerHTML = '<i class="fa-solid fa-heart"></i> Saved';
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
                    if (card) {
                        card.style.transition = "all 0.3s ease";
                        card.style.opacity = "0";
                        card.style.transform = "scale(0.92)";
                        setTimeout(() => {
                            card.remove();
                            const remaining = document.querySelectorAll(".recipe-card");
                            if (remaining.length === 0) {
                                const container = document.getElementById("favourites-container");
                                if (container) {
                                    container.innerHTML = `
                                        <div class="generator-card" style="text-align: center; padding: 60px 24px;">
                                            <div class="empty-icon-wrap">
                                                <i class="fa-regular fa-heart text-coral"></i>
                                            </div>
                                            <h2 style="font-size: 1.7rem; font-weight: 800; color: var(--text-primary); margin: 18px 0 10px;">No Favourite Recipes Yet</h2>
                                            <p style="color: var(--text-muted); max-width: 520px; margin: 0 auto 28px; font-size: 1.05rem;">
                                                You have no saved recipes in your collection.
                                            </p>
                                            <a href="/" class="btn btn-primary"><i class="fa-solid fa-plus"></i> Generate New Recipes</a>
                                        </div>
                                    `;
                                }
                            }
                        }, 300);
                    }

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

        let formatted = escapeHtml(text)
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n(\d+)\.\s/g, '<br><strong>$1.</strong> ')
            .replace(/\n[-•]\s/g, '<br>• ')
            .replace(/\n/g, '<br>');
        bubble.innerHTML = formatted;

        row.appendChild(bubble);
        chatMessages.appendChild(row);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function showTypingIndicator() {
        const row = document.createElement("div");
        row.className = "message-row bot-row typing-indicator-row";
        row.id = "typing-indicator";

        const bubble = document.createElement("div");
        bubble.className = "message-bubble typing-bubble";
        bubble.innerHTML = `
            <span class="typing-dots">
                <span></span><span></span><span></span>
            </span>
            <span style="font-size:0.84rem; color:var(--text-muted); margin-left:8px;">Chef AI is formulating an answer...</span>
        `;

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
        .then(res => {
            if (res.status === 401) {
                const modal = document.getElementById("chat-auth-modal");
                if (modal) modal.classList.add("open");
            }
            return res.json();
        })
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

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    // --------------------------------------------------------------------------
    // 7. API Key Setup Modal
    // --------------------------------------------------------------------------
    const apiModal = document.getElementById("api-key-modal");
    const openModalBtn = document.getElementById("open-api-modal");
    const bannerModalBtn = document.getElementById("banner-modal-trigger");
    const closeModalBtn = document.getElementById("close-api-modal");
    const closeModalActionBtn = document.getElementById("close-api-modal-btn");

    function openModal() {
        if (apiModal) apiModal.classList.add("open");
    }

    function closeModal() {
        if (apiModal) apiModal.classList.remove("open");
    }

    if (openModalBtn) openModalBtn.addEventListener("click", openModal);
    if (bannerModalBtn) bannerModalBtn.addEventListener("click", openModal);
    if (closeModalBtn) closeModalBtn.addEventListener("click", closeModal);
    if (closeModalActionBtn) closeModalActionBtn.addEventListener("click", closeModal);

    if (apiModal) {
        apiModal.addEventListener("click", function (e) {
            if (e.target === apiModal) {
                closeModal();
            }
        });
    }

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && apiModal && apiModal.classList.contains("open")) {
            closeModal();
        }
    });

    // --------------------------------------------------------------------------
    // 8. Mobile Navigation Toggle
    // --------------------------------------------------------------------------
    const navToggle = document.getElementById("nav-toggle");
    const navMenu = document.getElementById("nav-menu");

    if (navToggle && navMenu) {
        navToggle.addEventListener("click", function (e) {
            e.stopPropagation();
            const isOpen = navMenu.classList.toggle("open");
            navToggle.classList.toggle("open", isOpen);
            navToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
        });

        // Close mobile nav when clicking any nav link
        navMenu.querySelectorAll("a").forEach(function (link) {
            link.addEventListener("click", function () {
                navMenu.classList.remove("open");
                navToggle.classList.remove("open");
                navToggle.setAttribute("aria-expanded", "false");
            });
        });

        // Close when clicking outside
        document.addEventListener("click", function (e) {
            if (!navToggle.contains(e.target) && !navMenu.contains(e.target) && navMenu.classList.contains("open")) {
                navMenu.classList.remove("open");
                navToggle.classList.remove("open");
                navToggle.setAttribute("aria-expanded", "false");
            }
        });

        // Close on resize to desktop
        window.addEventListener("resize", function () {
            if (window.innerWidth > 768 && navMenu.classList.contains("open")) {
                navMenu.classList.remove("open");
                navToggle.classList.remove("open");
                navToggle.setAttribute("aria-expanded", "false");
            }
        });
    }
});

// Global Password Visibility Toggle
function togglePasswordVisibility(fieldId, btn) {
    const input = document.getElementById(fieldId);
    if (!input || !btn) return;
    const icon = btn.querySelector('i');
    if (input.type === 'password') {
        input.type = 'text';
        if (icon) {
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
        }
    } else {
        input.type = 'password';
        if (icon) {
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
        }
    }
}
