// QuestMart Chat V3 - customer support widget
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
      '<div id="qm-in"><input id="qm-input" placeholder="Ask..." autocomplete="off"><button id="qm-send">Send</button></div>' +
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

  addMessage('Hi! Welcome to QuestMart.online 🎮\nInstant delivery games & gift cards\nHow can I help?', 'qm-b');

  btn.onclick = function () {
    box.style.display = box.style.display === 'flex' ? 'none' : 'flex';
    if (box.style.display === 'flex') input.focus();
  };
  close.onclick = function () { box.style.display = 'none'; };

  function offlineReply(question) {
    var text = question.toLowerCase();
    if (text.indexOf('price') !== -1 || text.indexOf('قیمت') !== -1) {
      return 'All prices are listed on the product page. Which game or gift card are you looking for? 🎮';
    }
    if (text.indexOf('delivery') !== -1 || text.indexOf('تحویل') !== -1) {
      return 'Digital orders are delivered by email after payment. For order-specific help, contact support@questmart.online.';
    }
    if (text.indexOf('payment') !== -1 || text.indexOf('پرداخت') !== -1) {
      return 'Please use the secure checkout options shown on the product page. Contact support@questmart.online if you need help.';
    }
    return 'We offer games and gift cards with digital delivery. Tell me which product you want, or email support@questmart.online.';
  }

  async function ask(question) {
    if (!question) return;
    addMessage(question, 'qm-u');
    var loading = addMessage('Typing...', 'qm-b');
    try {
      var prompt = 'You are QuestMart.online support. We sell games and gift cards with digital delivery. Answer briefly in friendly English. Do not invent prices, order status, payment confirmation, refunds, or delivery guarantees. For account or order-specific help, direct the customer to support@questmart.online. User: ' + question;
      var url = 'https://text.pollinations.ai/' + encodeURIComponent(prompt) + '?model=openai';
      var response = await fetch(url, { method: 'GET', headers: { 'Accept': 'text/plain' } });
      if (!response.ok) throw new Error('AI request failed: HTTP ' + response.status);
      var answer = (await response.text()).trim();
      if (!answer || /temporarily unavailable|service unavailable/i.test(answer)) throw new Error('Empty AI response');
      loading.remove();
      addMessage(answer, 'qm-b');
    } catch (error) {
      loading.remove();
      addMessage(offlineReply(question), 'qm-b');
      console.error('QuestMart chat error:', error);
    }
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
