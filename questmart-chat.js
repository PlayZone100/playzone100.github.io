// QuestMart Chat V4 - offline English rule-based support
(function () {
  'use strict';

  var css = '#qm-btn{position:fixed;bottom:20px;right:20px;width:60px;height:60px;background:#7c3aed;color:#fff;border-radius:50%;border:none;font-size:28px;cursor:pointer;z-index:99999;box-shadow:0 8px 20px rgba(124,58,237,.4)}#qm-box{position:fixed;bottom:90px;right:20px;width:360px;max-width:92vw;height:460px;background:#fff;border-radius:16px;box-shadow:0 10px 40px rgba(0,0,0,.3);display:none;flex-direction:column;z-index:99999;font-family:sans-serif;overflow:hidden;border:1px solid #eee}#qm-head{background:#7c3aed;color:#fff;padding:14px;font-weight:bold;display:flex;justify-content:space-between}#qm-msgs{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;background:#fafafa}.qm-m{padding:10px 12px;border-radius:12px;max-width:82%;font-size:14px;line-height:1.5;white-space:pre-wrap}.qm-u{align-self:flex-end;background:#7c3aed;color:#fff}.qm-b{align-self:flex-start;background:#fff;border:1px solid #ddd;color:#111}#qm-in{display:flex;padding:10px;border-top:1px solid #eee;gap:6px}#qm-in input{flex:1;padding:10px;border:1px solid #ddd;border-radius:8px}#qm-in button{padding:10px 14px;background:#7c3aed;color:#fff;border:none;border-radius:8px;cursor:pointer}';
  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  var wrapper = document.createElement('div');
  wrapper.innerHTML = '<button id="qm-btn" aria-label="Open QuestMart support">🎮</button>' +
    '<div id="qm-box" role="dialog" aria-label="QuestMart Support">' +
      '<div id="qm-head"><span>QuestMart Support</span><button id="qm-x" aria-label="Close" style="cursor:pointer;background:none;border:0;color:#fff;font-size:16px">✕</button></div>' +
      '<div id="qm-msgs"></div>' +
      '<div id="qm-in"><input id="qm-input" placeholder="Ask about games, delivery or payment..." autocomplete="off"><button id="qm-send">Send</button></div>' +
    '</div>';
  document.body.appendChild(wrapper);

  var btn = document.getElementById('qm-btn');
  var box = document.getElementById('qm-box');
  var close = document.getElementById('qm-x');
  var input = document.getElementById('qm-input');
  var send = document.getElementById('qm-send');
  var messages = document.getElementById('qm-msgs');

  function addMessage(text, className) {
    var element = document.createElement('div');
    element.className = 'qm-m ' + className;
    element.textContent = text;
    messages.appendChild(element);
    messages.scrollTop = messages.scrollHeight;
    return element;
  }

  function reply(question) {
    var q = question.toLowerCase();
    if (/delivery|deliver|instant|تحویل/.test(q)) {
      return 'Instant digital delivery! Orders are usually delivered within 2-5 minutes after successful payment. For order-specific help, email support@questmart.online.';
    }
    if (/payment|pay|card|crypto|paypal|پرداخت/.test(q)) {
      return 'We accept the secure checkout methods shown on the product page, including available card, PayPal, or crypto options. Never send payment details in chat.';
    }
    if (/legit|trusted|scam|safe|واقعی|اعتماد/.test(q)) {
      return 'QuestMart is an independent digital marketplace. Check the product details and contact support@questmart.online before purchasing if you have questions.';
    }
    if (/fortnite|v-buck|v buck/.test(q)) {
      return 'Please check the marketplace for currently available Fortnite gift cards or V-Bucks products. Availability and prices are shown on each product page.';
    }
    if (/price|cost|cheap|قیمت/.test(q)) {
      return 'Prices are listed on each product page. Tell me the game or gift card name and I can guide you to the right section.';
    }
    if (/game|gift|card|product|بازی/.test(q)) {
      return 'We offer browser games and digital products. Tell me what game or gift card you are looking for and I will help you find it.';
    }
    if (/refund|cancel|order|account|بازگشت/.test(q)) {
      return 'For an order, account, refund, or cancellation request, please email support@questmart.online with your order details. Do not share passwords here.';
    }
    return 'Welcome to QuestMart! We offer games and digital products with online support. Ask about delivery, payment, prices, or a specific game.';
  }

  addMessage('Hi! Welcome to QuestMart.online 🎮\nGames, gift cards and digital products.\nHow can I help you today?', 'qm-b');
  btn.onclick = function () {
    box.style.display = box.style.display === 'flex' ? 'none' : 'flex';
    if (box.style.display === 'flex') input.focus();
  };
  close.onclick = function () { box.style.display = 'none'; };

  function ask(question) {
    if (!question) return;
    addMessage(question, 'qm-u');
    var loading = addMessage('Typing...', 'qm-b');
    window.setTimeout(function () {
      loading.remove();
      addMessage(reply(question), 'qm-b');
    }, 250);
  }

  send.onclick = function () {
    var value = input.value.trim();
    input.value = '';
    ask(value);
  };
  input.addEventListener('keydown', function (event) {
    if (event.key === 'Enter') send.click();
  });
})();
