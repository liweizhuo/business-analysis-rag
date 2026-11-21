// 与参考页面保持相同布局；请求接入新工程 /api/ask，不连接旧演示接口。
const $ = s => document.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const titles = {ask:'智能问答',report:'生成周报',search:'查业务规则'};
document.querySelectorAll('.nav-item').forEach(b => b.onclick = () => {
  document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n === b));
  document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.id === b.dataset.page+'Page'));
  $('#pageTitle').textContent = titles[b.dataset.page];
  $('.sidebar').classList.remove('open');
});
$('#menuButton').onclick = () => $('.sidebar').classList.toggle('open');
function toast(message) {
  $('#toast').textContent = message; $('#toast').classList.add('show');
  setTimeout(() => $('#toast').classList.remove('show'), 5000);
}
async function request(question) {
  const response = await fetch('/api/ask', {method:'POST',
    headers:{'Content-Type':'application/json','X-API-Key':$('#accessKey').value},
    body:JSON.stringify({question})});
  const result = await response.json();
  if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : '请求失败');
  return result;
}
function evidenceHtml(items) {
  return items.map(e => `<details class="evidence"><summary>${esc(e.source_file)} · 第${esc(e.start_line)}—${esc(e.end_line)}行</summary><p>引用：${esc(e.evidence_id)} · 版本：${esc(e.document_version)}</p><p>${esc(e.parent_content)}</p></details>`).join('');
}
async function ask() {
  const question = $('#question').value.trim();
  if (!question) return toast('请输入问题');
  if ($('#askButton').disabled) return;
  $('#askButton').disabled = true; $('#askLoading').classList.remove('hidden');
  $('#askResult').classList.add('hidden');
  try {
    const result = await request(question);
    $('#answerText').textContent = result.answer;
    $('#evidenceList').innerHTML = evidenceHtml(result.evidence || []);
    $('#dataCard').classList.toggle('hidden', !result.sql);
    $('#sqlText').textContent = result.sql || '';
    const rows = result.rows || [], columns = Object.keys(rows[0] || {});
    $('#dataTable').innerHTML = `<table><thead><tr>${columns.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${columns.map(c=>`<td>${esc(r[c])}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
    $('#askResult').classList.remove('hidden');
  } catch (error) { toast(error.message); }
  finally { $('#askButton').disabled = false; $('#askLoading').classList.add('hidden'); }
}
$('#askButton').onclick = ask;
$('#question').onkeydown = e => {if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {e.preventDefault();ask();}};
document.querySelectorAll('.example').forEach(b => b.onclick = () => {$('#question').value=b.dataset.question;ask();});
// 规则入口复用口径问答链路，不暴露未经授权的独立检索端点。
async function search() {
  const q = $('#searchQuery').value.trim(); if (!q) return toast('请输入业务规则问题');
  $('#searchButton').disabled = true;
  try {
    const result = await request('请仅说明业务口径，不查询金额：'+q);
    $('#searchResult').innerHTML = `<article class="card search-hit"><h3>口径说明</h3><p>${esc(result.answer)}</p></article>` + evidenceHtml(result.evidence || []);
  } catch (error) {toast(error.message);}
  finally {$('#searchButton').disabled=false;}
}
$('#searchButton').onclick=search;
$('#searchQuery').onkeydown=e=>{if(e.key==='Enter'&&!e.isComposing)search();};
$('#reportForm').onsubmit=e=>e.preventDefault();
const now=new Date();
$('#reportYear').value=now.getFullYear();$('#reportQuarter').value='Q'+(Math.floor(now.getMonth()/3)+1);
const day=new Date(Date.UTC(now.getFullYear(),now.getMonth(),now.getDate()));
day.setUTCDate(day.getUTCDate()+4-(day.getUTCDay()||7));
$('#reportWeek').value=Math.ceil(((day-new Date(Date.UTC(day.getUTCFullYear(),0,1)))/86400000+1)/7);
fetch('/health').then(r=>{if(!r.ok)throw Error();return r.json();}).then(()=>{
  $('#statusDot').classList.add('ok');$('#statusText').textContent='网页服务已连接';
}).catch(()=>{$('#statusText').textContent='网页服务未连接';});
