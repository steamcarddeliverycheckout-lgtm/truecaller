<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>CC Checker - Gate Validator</title>
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    
    body {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      padding: 20px;
      display: flex;
      justify-content: center;
      align-items: center;
    }
    
    .container {
      max-width: 900px;
      width: 100%;
      background: rgba(255, 255, 255, 0.95);
      border-radius: 20px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
      padding: 40px;
      backdrop-filter: blur(10px);
    }
    
    h1 {
      text-align: center;
      color: #667eea;
      font-size: 2.5em;
      margin-bottom: 10px;
      font-weight: 700;
    }
    
    .subtitle {
      text-align: center;
      color: #666;
      margin-bottom: 30px;
      font-size: 1.1em;
    }
    
    .input-section {
      margin-bottom: 30px;
    }
    
    .input-label {
      display: block;
      margin-bottom: 10px;
      color: #333;
      font-weight: 600;
      font-size: 1.1em;
    }
    
    .card-input, .cards-textarea {
      width: 100%;
      padding: 15px 20px;
      border: 2px solid #e0e0e0;
      border-radius: 12px;
      font-size: 16px;
      transition: all 0.3s ease;
      font-family: monospace;
    }
    
    .card-input:focus {
      outline: none;
      border-color: #667eea;
      box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    .cards-textarea {
      min-height: 120px;
      resize: vertical;
    }
    
    .gates-container {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
      margin-bottom: 30px;
    }
    
    .gate-section {
      background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
      border-radius: 15px;
      padding: 25px;
      box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
    }
    
    .gate-title {
      font-size: 1.3em;
      font-weight: 700;
      color: #333;
      margin-bottom: 15px;
      text-align: center;
      padding-bottom: 10px;
      border-bottom: 2px solid rgba(102, 126, 234, 0.3);
    }
    
    .gate-buttons {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    
    .gate-btn {
      padding: 15px 25px;
      border: none;
      border-radius: 12px;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.3s ease;
      box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
      color: white;
      position: relative;
      overflow: hidden;
    }
    
    .gate-btn:before {
      content: '';
      position: absolute;
      top: 50%;
      left: 50%;
      width: 0;
      height: 0;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.3);
      transform: translate(-50%, -50%);
      transition: width 0.6s, height 0.6s;
    }
    
    .gate-btn:hover:before {
      width: 300px;
      height: 300px;
    }
    
    .gate-btn:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2);
    }
    
    .gate-btn:active {
      transform: translateY(0);
    }
    
    .stripe-btn {
      background: linear-gradient(135deg, #6772e5 0%, #5469d4 100%);
    }
    
    .braintree-btn {
      background: linear-gradient(135deg, #00c9a7 0%, #00a88f 100%);
    }
    
    .paypal-btn {
      background: linear-gradient(135deg, #0070ba 0%, #005ea6 100%);
    }
    
    .shopify-btn {
      background: linear-gradient(135deg, #95bf47 0%, #7ab800 100%);
    }
    
    #result {
      margin-top: 25px;
      padding: 20px;
      border-radius: 12px;
      background: #f8f9fa;
      border-left: 4px solid #667eea;
      display: none;
    }
    
    #result.show {
      display: block;
      animation: slideIn 0.3s ease;
    }
    
    @keyframes slideIn {
      from {
        opacity: 0;
        transform: translateY(-10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    
    .result-title {
      font-weight: 700;
      color: #333;
      margin-bottom: 10px;
      font-size: 1.2em;
    }
    
    .result-content {
      background: white;
      padding: 15px;
      border-radius: 8px;
      white-space: pre-wrap;
      word-wrap: break-word;
      font-family: 'Courier New', monospace;
      font-size: 14px;
      line-height: 1.6;
      color: #333;
      max-height: 400px;
      overflow-y: auto;
    }
    
    .loading {
      text-align: center;
      color: #667eea;
      font-size: 1.2em;
      padding: 20px;
    }
    
    .spinner {
      border: 3px solid #f3f3f3;
      border-top: 3px solid #667eea;
      border-radius: 50%;
      width: 40px;
      height: 40px;
      animation: spin 1s linear infinite;
      margin: 20px auto;
    }
    
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    
    .error {
      background: #fee;
      border-left-color: #f44336;
      color: #d32f2f;
    }
    
    .success {
      background: #e8f5e9;
      border-left-color: #4caf50;
    }
    
    @media (max-width: 768px) {
      .gates-container {
        grid-template-columns: 1fr;
      }
      
      .container {
        padding: 25px;
      }
      
      h1 {
        font-size: 2em;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>💳 CC Gate Checker</h1>
    <p class="subtitle">Validate credit cards through multiple payment gates</p>
    
    <div class="input-section">
      <label class="input-label">Enter Card Details (single):</label>
      <input 
        id="cardInput" 
        type="text" 
        class="card-input" 
        placeholder="5333499418581618|03|29|232"
        autocomplete="off"
      >
      <small style="color: #666; margin-top: 5px; display: block;">Format: card_number|month|year|cvv</small>
    </div>
    
    <div class="input-section">
      <label class="input-label">Enter Multiple Cards (one per line):</label>
      <textarea id="cardsTextarea" class="cards-textarea" placeholder="5333499418581618|03|29|232\n4556737586899855|05|2028|123\n..."></textarea>
      <small style="color: #666; margin-top: 5px; display: block;">We'll process them sequentially and return per-card results.</small>
    </div>
    
    <div class="gates-container">
      <div class="gate-section">
        <div class="gate-title">🔐 Auth Gate</div>
        <div class="gate-buttons">
          <button class="gate-btn stripe-btn" onclick="checkCard('stripe')">
            <span>Stripe Auth</span>
          </button>
          <button class="gate-btn braintree-btn" onclick="checkCard('braintree')">
            <span>Braintree Auth</span>
          </button>
          <button class="gate-btn stripe-btn" onclick="checkCardsBatch('stripe')">
            <span>Stripe Auth (Batch)</span>
          </button>
          <button class="gate-btn braintree-btn" onclick="checkCardsBatch('braintree')">
            <span>Braintree Auth (Batch)</span>
          </button>
        </div>
      </div>
      
      <div class="gate-section">
        <div class="gate-title">💰 Charge Gate</div>
        <div class="gate-buttons">
          <button class="gate-btn paypal-btn" onclick="checkCard('paypal')">
            <span>PayPal Charge</span>
          </button>
          <button class="gate-btn shopify-btn" onclick="checkCard('shopify')">
            <span>Shopify Charge</span>
          </button>
          <button class="gate-btn paypal-btn" onclick="checkCardsBatch('paypal')">
            <span>PayPal Charge (Batch)</span>
          </button>
          <button class="gate-btn shopify-btn" onclick="checkCardsBatch('shopify')">
            <span>Shopify Charge (Batch)</span>
          </button>
        </div>
      </div>
    </div>
    
    <div id="result"></div>
  </div>

  <script>
    async function checkCard(gateType) {
      const cardInput = document.getElementById("cardInput").value.trim();
      const resultDiv = document.getElementById("result");
      
      if (!cardInput) {
        showResult("Please enter card details!", "error");
        return;
      }
      
      // Validate card format
      const cardPattern = /^\d{13,19}\|\d{2}\|\d{2,4}\|\d{3,4}$/;
      if (!cardPattern.test(cardInput)) {
        showResult("Invalid card format! Use: number|month|year|cvv", "error");
        return;
      }
      
      // Show loading
      resultDiv.className = "show";
      resultDiv.innerHTML = `
        <div class="loading">
          <div class="spinner"></div>
          <p>Processing ${gateType.toUpperCase()} gate...</p>
        </div>
      `;
      
      try {
        const response = await fetch(window.location.origin + "/cc-check", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            card: cardInput,
            gate_type: gateType
          })
        });
        
        const data = await response.json();
        
        if (data.ok && data.raw) {
          showResult(data.raw, "success");
        } else if (data.ok && data.full_response) {
          // Fallback to full response if cleaning failed
          showResult(data.full_response, "success");
        } else {
          const errorMsg = data.detail || JSON.stringify(data);
          showResult("Error: " + errorMsg, "error");
        }
      } catch (err) {
        showResult("Network Error: " + err.message, "error");
      }
    }
    
    function showResult(content, type) {
      const resultDiv = document.getElementById("result");
      const className = type === "error" ? "error show" : "success show";
      const title = type === "error" ? "❌ Error" : "✅ Response";
      
      resultDiv.className = className;
      resultDiv.innerHTML = `
        <div class="result-title">${title}</div>
        <div class="result-content">${escapeHtml(content)}</div>
      `;
    }
    
    function escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }
    
    // Allow Enter key to submit
    document.getElementById("cardInput").addEventListener("keypress", function(e) {
      if (e.key === "Enter") {
        // Default to stripe if Enter is pressed
        checkCard('stripe');
      }
    });
    async function checkCardsBatch(gateType) {
      const textarea = document.getElementById("cardsTextarea");
      const resultDiv = document.getElementById("result");
      const lines = textarea.value.split(/\n+/).map(s => s.trim()).filter(Boolean);

      if (!lines.length) {
        showResult("Please enter at least one card (one per line).", "error");
        return;
      }

      // Show loading
      resultDiv.className = "show";
      resultDiv.innerHTML = `
        <div class=\"loading\">\n          <div class=\"spinner\"></div>\n          <p>Processing ${lines.length} cards via ${gateType.toUpperCase()}...</p>\n        </div>
      `;

      try {
        const response = await fetch(window.location.origin + "/cc-check-batch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            cards: lines,
            gate_type: gateType
          })
        });
        const data = await response.json();

        if (data.ok && Array.isArray(data.results)) {
          let html = '<div class=\"result-title\">✅ Batch Results</div>';
          html += '<div class=\"result-content\">';
          data.results.forEach((r, idx) => {
            html += `\n#${idx+1} — ${escapeHtml(r.card)}\n`;
            if (r.ok) {
              html += `${escapeHtml(r.raw)}\n`;
            } else {
              html += `Error: ${escapeHtml(r.error || 'Unknown error')}\n`;
            }
            html += `\n`;
          });
          html += '</div>';
          resultDiv.className = "success show";
          resultDiv.innerHTML = html;
        } else {
          const errorMsg = data.detail || JSON.stringify(data);
          showResult("Error: " + errorMsg, "error");
        }
      } catch (err) {
        showResult("Network Error: " + err.message, "error");
      }
    }
  </script>
</body>
</html>

