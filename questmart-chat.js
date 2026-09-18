// QuestMart Chat - customer support widget
(function () {
  'use strict';

  var css = '\n' +
    '#qm-btn{position:fixed;bottom:20px;right:20px;width:60px;height:60px;background:#7c3aed;color:#fff;border-radius:50%;border:none;font-size:28px;cursor:pointer;z-index:99999;box-shadow:0 8px 20px rgba(124,58,237,.4)}\n' +
    '#qm-box{position:fixed;bottom:90px;right:20px;width:360px;max-width:92vw;height:480px;background:#fff;border-radius:16px;box-shadow:0 10px 40px rgba(0,0,0,.25);display:none;flex-direction:column;z-index:99999;font-family:sans-serif;overflow:hidden;border:1px solid #eee}\n' +
    '#qm-head{background:#7c3aed;color:#fff;padding:14px;font-weight:bold;display:flex;justify-content:space-between}\n' +
    '#qm-msgs{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;background:#fafafa}\n' +
    '.qm-m{padding:10px 12px;border-radius:12px;max-width:80%;font-size:14px;line-height:1.4;white-space:pre-wrap}\n' +
    '.qm-u{align-self:flex-end;background:#7c3aed;color:#fff}\n' +
    '.qm-b{align-self:flex-start;background:#fff;border:1px solid #ddd;color:#111}\n' +
    '#qm-in{display:flex;padding:10px;border-top:1px solid #eee;gap:6px}\n' +
    '#qm-in input{flex:1;padding:10px;border:1px solid #ddd;border-radius:8px}\n' +
    '#qm-in button{padding:10px 14px;background:#7c3aed;color:#fff;border:none;border-radius:8px;cursor:pointer}\n';

  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  var wrapper = document.createElement('div');
  wrapper.innerHTML =
    '<button id="qm-btn" aria-label="Open QuestMart support">🎮</button>' +
    '<div id="qm-box" role="dialog" aria-label="QuestMart Support">' +
      '<div id="qm-head"><span>QuestMart Support</span><button id="qm-x" aria-label="Close" style="cursor:pointer;background:none;border:0;color:#fff;font-size:16px">✕</button></div>' +
      '<div id="qm-msgs"></div>' +
      '<div id="qm-in"><input id="qm-input" placeholder="Type your question..." autocomplete="off"><button id="qm-send">Send</button></div>' +
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

  addMessage('Hi! Welcome to QuestMart.online 🌍\nGames, Gift Cards & Digital Files - Instant Delivery!\nHow can I help you?', 'qm-b');

  btn.onclick = function () {
    box.style.display = box.style.display === 'flex' ? 'none' : 'flex';
    if (box.style.display === 'flex') input.focus();
  };
  close.onclick = function () { box.style.display = 'none'; };

  async function ask(question) {
    if (!question) return;
    addMessage(question, 'qm-u');
    var loading = addMessage('Typing...', 'qm-b');
    try {
      if (typeof window.puter === 'undefined' || !puter.ai) throw new Error('Puter is not ready');
      var prompt = 'You are QuestMart.online support. We sell games, gift cards, accounts, and digital files. Instant delivery, secure payment. Answer briefly and in friendly English. Do not invent order status or promise refunds. User: ' + question;
      var response = await puter.ai.chat(prompt, { model: 'gpt-4o-mini' });
      loading.remove();
      var answer = typeof response === 'string' ? response : (response && response.message && response.message.content) || 'Please contact support@questmart.online for help.';
      addMessage(answer, 'qm-b');
    } catch (error) {
      loading.remove();
      addMessage('Sorry, chat is temporarily unavailable. Please email support@questmart.online.', 'qm-b');
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
