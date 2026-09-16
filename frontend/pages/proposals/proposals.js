/* The proposals screen: table, filters, drawer, add/edit modal.
   Moved verbatim from Bhumijo_Proposal_Tracker_22Jul2026.html — 39 function(s), not rewritten.
   Loaded in a fixed order by index.html, sharing one scope, exactly as before. */

function filterTable() {
  const q=(document.getElementById('search-input').value||'').toLowerCase();
  const entity=document.getElementById('filter-entity').value;
  const status=document.getElementById('filter-status').value;
  const result=document.getElementById('filter-result').value;
  const startVal=(document.getElementById('filter-start-date')||{}).value||'';
  const endVal=(document.getElementById('filter-end-date')||{}).value||'';
  const dateFrom = startVal ? new Date(startVal+'T00:00:00') : null;
  const dateTo   = endVal   ? new Date(endVal+'T23:59:59')   : null;
  filteredData=proposals.filter(p=>{
    if(entity&&p.entity!==entity)return false;
    if(!matchesStatusFilter(p,status))return false;
    if(result&&p.result!==result)return false;
    if(dateFrom||dateTo){
      const dRaw=p.closeDate||p.createdAt||'';
      if(!dRaw)return false;
      const d=new Date(dRaw+'T00:00:00');
      if(dateFrom&&d<dateFrom)return false;
      if(dateTo&&d>dateTo)return false;
    }
    if(q&&!p.title.toLowerCase().includes(q)&&!(p.client||'').toLowerCase().includes(q)&&!(p.responsible||'').toLowerCase().includes(q))return false;
    return true;
  });
  filteredData.sort((a,b)=>{
    if(sortField==='closeDate'){
      const rank=p=>{
        if(!p.closeDate)return Infinity;
        const today=new Date();today.setHours(0,0,0,0);
        const close=new Date(p.closeDate+'T00:00:00');
        if(isNaN(close))return Infinity;
        const diff=Math.ceil((close-today)/86400000);
        return diff>=0?diff:100000+Math.abs(diff);
      };
      const ar=rank(a),br=rank(b);
      return sortDir==='asc'?ar-br:br-ar;
    }
    let av=a[sortField]||'',bv=b[sortField]||'';
    if(sortDir==='asc')return av.localeCompare(bv);
    return bv.localeCompare(av);
  });
  currentPage=1;
  renderTablePage();
}

function sortBy(field) {
  if(sortField===field)sortDir=sortDir==='asc'?'desc':'asc';
  else{sortField=field;sortDir='asc';}
  filterTable();
}

function renderTablePage() {
  const start=(currentPage-1)*PAGE_SIZE,end=start+PAGE_SIZE,page=filteredData.slice(start,end);
  const tbody=document.getElementById('main-tbody');
  if(!page.length){
    tbody.innerHTML='<tr><td colspan="8"><div class="empty-state"><div class="icon">◎</div><p>No proposals match your filters.</p></div></td></tr>';
    document.getElementById('page-info').textContent='0 results';
    document.getElementById('page-controls').innerHTML='';
    return;
  }
  tbody.innerHTML=page.map(p=>{
    const remarkFull=p.remark||'';
    return `<tr onclick="openDrawer('${p.id}')">
      <td class="td-title">
        <span class="td-title-text" title="${esc(p.title)}">${esc(p.title)}</span>
        <div class="td-meta">Client: ${esc(p.client||'–')}</div>
        <div class="td-value">Value: ${esc(p.value||'–')}</div>
      </td>
      <td><span class="entity-badge entity-${p.entity.replace('&','')}">${p.entity}</span></td>
      <td>${stageBadge(p.category)}</td>
      <td>${daysBadge(p.closeDate)}</td>
      <td style="font-size:12px;color:var(--text2);white-space:nowrap">${fmtDate(p.closeDate)}</td>
      <td>${statusBadge(p.status)} ${resultBadge(p.result)}</td>
      <td style="font-size:12px;color:var(--text2);max-width:110px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(p.responsible||'–')}</td>
      <td style="font-size:11px;color:var(--text3);max-width:280px;white-space:normal;overflow-wrap:break-word">${esc(remarkFull)||'–'}</td>
    </tr>`;
  }).join('');
  const total=filteredData.length;
  document.getElementById('page-info').textContent=`Showing ${start+1}–${Math.min(end,total)} of ${total}`;
  renderPagination(total);
}

function renderPagination(total) {
  const pages=Math.ceil(total/PAGE_SIZE);
  const ctrl=document.getElementById('page-controls');
  if(pages<=1){ctrl.innerHTML='';return;}
  let html=`<button class="page-btn" onclick="goPage(${currentPage-1})" ${currentPage===1?'disabled':''}>‹</button>`;
  for(let i=1;i<=pages;i++){
    if(i===1||i===pages||Math.abs(i-currentPage)<=2)html+=`<button class="page-btn ${i===currentPage?'active-page':''}" onclick="goPage(${i})">${i}</button>`;
    else if(Math.abs(i-currentPage)===3)html+=`<span style="color:var(--text3);padding:0 4px">…</span>`;
  }
  html+=`<button class="page-btn" onclick="goPage(${currentPage+1})" ${currentPage===pages?'disabled':''}>›</button>`;
  ctrl.innerHTML=html;
}
function goPage(n){currentPage=n;renderTablePage();}

// ─── CLIENTS ──────────────────────────────────────────────────────────────────
function openDrawer(id) {
  const p=proposals.find(x=>x.id===id);
  if(!p)return;
  document.getElementById('drawer-title').textContent=p.title;
  const today=new Date();today.setHours(0,0,0,0);
  const daysLeft=p.closeDate?Math.ceil((new Date(p.closeDate)-today)/86400000):null;
  document.getElementById('drawer-body').innerHTML=`
    <div class="drawer-section">
      <div class="tag-row">
        <span class="entity-badge entity-${p.entity.replace('&','')}">${p.entity}</span>
        ${statusBadge(p.status)} ${resultBadge(p.result)}
        ${p.contract==='Yes'?'<span class="badge badge-accepted">Contract Signed</span>':''}
      </div>
    </div>
    <div class="drawer-section">
      <div class="drawer-section-label">Details</div>
      <div class="drawer-field"><span class="drawer-field-label">Category</span><span class="drawer-field-value">${esc(p.category||'–')}</span></div>
      <div class="drawer-field"><span class="drawer-field-label">Client / Funder</span><span class="drawer-field-value">${esc(p.client||'–')}</span></div>
      ${p.value?`<div class="drawer-field"><span class="drawer-field-label">Project Value</span><span class="drawer-field-value" style="color:var(--green);font-weight:600;font-family:'JetBrains Mono',monospace">${esc(p.value)}</span></div>`:''}
      <div class="drawer-field"><span class="drawer-field-label">Responsible</span><span class="drawer-field-value">${esc(p.responsible||'–')}</span></div>
      ${p.fileLoc?`<div class="drawer-field"><span class="drawer-field-label">File Location</span><span class="drawer-field-value">${esc(p.fileLoc)}</span></div>`:''}
      <div class="drawer-field"><span class="drawer-field-label">Opening Date</span><span class="drawer-field-value">${fmtDate(p.openDate)}</span></div>
      <div class="drawer-field"><span class="drawer-field-label">Closing Date</span><span class="drawer-field-value">${fmtDate(p.closeDate)}${daysLeft!==null?' ('+daysLeft+' days)':'' }</span></div>
      ${p.startDate?`<div class="drawer-field"><span class="drawer-field-label">Project Start</span><span class="drawer-field-value">${fmtDate(p.startDate)}</span></div>`:''}
      ${p.endDate?`<div class="drawer-field"><span class="drawer-field-label">Project End</span><span class="drawer-field-value">${fmtDate(p.endDate)}</span></div>`:''}
    </div>
    ${p.remark?`<div class="drawer-section"><div class="drawer-section-label">Notes & Updates</div><div class="drawer-remark">${esc(p.remark).replace(/\|/g,'<br>•')}</div></div>`:''}
  `;
  document.getElementById('drawer-actions').innerHTML=`
    <button class="btn btn-ghost" onclick="openEditModal('${id}')">✏ Edit</button>
    <button class="btn btn-danger" onclick="confirmDelete('${id}')">✕ Delete</button>
  `;
  document.getElementById('drawer-overlay').classList.add('open');
  document.getElementById('detail-drawer').classList.add('open');
}
function closeDrawer(){document.getElementById('drawer-overlay').classList.remove('open');document.getElementById('detail-drawer').classList.remove('open');}

// ─── MODAL ────────────────────────────────────────────────────────────────────
function openAddModal(withUpload=true) {
  editingId=null;
  document.getElementById('modal-title').textContent='New Proposal';
  document.getElementById('modal-sub').textContent='Upload a document to auto-fill, or enter details manually.';
  document.getElementById('upload-zone').style.display=withUpload===false?'none':'block';
  clearForm();
  document.getElementById('proposal-modal').classList.add('open');
}

function openEditModal(id) {
  closeDrawer();
  const p=proposals.find(x=>x.id===id);
  if(!p)return;
  editingId=id;
  document.getElementById('modal-title').textContent='Edit Proposal';
  document.getElementById('modal-sub').textContent=`Editing: ${p.title.substring(0,55)}`;
  document.getElementById('upload-zone').style.display='none';
  clearForm();
  document.getElementById('f-title').value=p.title;
  document.getElementById('f-entity').value=p.entity;
  document.getElementById('f-category').value=p.category||'';
  document.getElementById('f-client').value=p.client||'';
  document.getElementById('f-value').value=p.value||'';
  document.getElementById('f-responsible').value=p.responsible||'';
  document.getElementById('f-fileLoc').value=p.fileLoc||'';
  document.getElementById('f-openDate').value=p.openDate||'';
  document.getElementById('f-closeDate').value=p.closeDate||'';
  let statusValue=p.status;
  if(p.status==='Submitted' && p.result){
    const match=Object.entries(COMPOUND_STATUS_RESULT_MAP).find(([k,v])=>v===p.result);
    if(match) statusValue=match[0];
  }
  document.getElementById('f-status').value=statusValue;
  onStatusChange();
  document.getElementById('f-contract').value=p.contract||'';
  document.getElementById('f-startDate').value=p.startDate||'';
  document.getElementById('f-endDate').value=p.endDate||'';
  document.getElementById('f-remark').value=p.remark||'';
  document.getElementById('proposal-modal').classList.add('open');
}
function closeModal(){document.getElementById('proposal-modal').classList.remove('open');editingId=null;}

// ─── FILE UPLOAD / AI PARSE ───────────────────────────────────────────────────
function onDragOver(e){e.preventDefault();document.getElementById('upload-zone').classList.add('dragover');}
function onDragLeave(e){document.getElementById('upload-zone').classList.remove('dragover');}
function onDrop(e){e.preventDefault();document.getElementById('upload-zone').classList.remove('dragover');const files=e.dataTransfer.files;if(files.length)processUploadedFile(files[0]);}
function handleFileUpload(e){if(e.target.files.length)processUploadedFile(e.target.files[0]);}

async function processUploadedFile(file) {
  const status=document.getElementById('upload-status');
  status.className='upload-status upload-parsing';
  status.textContent=`Reading ${file.name}…`;
  try {
    let text='';
    if(file.type==='text/plain'){
      text=await file.text();
    } else if(file.type.startsWith('image/')){
      text=`[Image: ${file.name}]`;
    } else {
      // For PDF/DOCX read as text best-effort
      text=await file.text().catch(()=>`[File: ${file.name}]`);
    }
    status.className='upload-status upload-parsing';
    status.textContent='Extracting proposal details with AI…';
    const extracted=await extractWithClaude(text.substring(0,8000), file.name);
    applyExtractedFields(extracted);
    status.className='upload-status';
    status.textContent='✓ Fields extracted. Please review and fill any blanks.';
    toast('Document processed. Please review extracted fields.','success');
  } catch(err) {
    status.className='upload-status';
    status.textContent='Could not auto-extract. Please fill fields manually.';
    toast('Could not parse document. Please fill fields manually.','error');
  }
}

async function extractWithClaude(text, filename) {
  const prompt=`You are a proposal data extraction assistant. Extract structured information from the following proposal document text and return ONLY a valid JSON object with these exact keys (use empty string if not found):
{
  "title": "proposal or project title",
  "client": "client or funder organisation name",
  "category": "one of: EOI, RFP, RFQ, Tender, Proposal, Proposal & Work, Presentation, Meeting, General, Consultancy",
  "entity": "one of: P&D, FM, WASH, Tech (guess from context: P&D=design/architecture/urban, FM=facility/cleaning/manpower, WASH=toilet/sanitation, Tech=technology)",
  "openDate": "YYYY-MM-DD or empty",
  "closeDate": "YYYY-MM-DD or empty",
  "value": "project value with currency if mentioned, else empty",
  "responsible": "responsible person or team if mentioned",
  "remark": "brief summary of key information from the document"
}
Document filename: ${filename}
Document text:
${text}`;

  const response=await fetch('https://api.anthropic.com/v1/messages',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      model:'claude-sonnet-4-6',
      max_tokens:1000,
      messages:[{role:'user',content:prompt}]
    })
  });
  if(!response.ok) throw new Error('API error');
  const data=await response.json();
  const raw=data.content.filter(b=>b.type==='text').map(b=>b.text).join('');
  // Strip markdown fences if present
  const clean=raw.replace(/```json|```/g,'').trim();
  return JSON.parse(clean);
}

function applyExtractedFields(fields) {
  if(fields.title)document.getElementById('f-title').value=fields.title;
  if(fields.client)document.getElementById('f-client').value=fields.client;
  if(fields.value)document.getElementById('f-value').value=fields.value;
  if(fields.responsible)document.getElementById('f-responsible').value=fields.responsible;
  if(fields.openDate)document.getElementById('f-openDate').value=fields.openDate;
  if(fields.closeDate)document.getElementById('f-closeDate').value=fields.closeDate;
  if(fields.remark)document.getElementById('f-remark').value=fields.remark;
  // Entity
  if(fields.entity){const el=document.getElementById('f-entity');el.value=fields.entity;if(!el.value)el.value=''; }
  // Category
  if(fields.category){document.getElementById('f-category').value=fields.category;}
}

// ─── FORM HELPERS ─────────────────────────────────────────────────────────────
function clearFieldError(groupId){const g=document.getElementById(groupId);if(!g)return;g.classList.remove('field-error');const h=g.querySelector('.field-hint');if(h)h.classList.remove('error','info');}
function setFieldError(groupId,hintId){const g=document.getElementById(groupId),h=document.getElementById(hintId);if(g)g.classList.add('field-error');if(h)h.classList.add('error');return g;}

const COMPOUND_STATUS_RESULT_MAP={
  'Submitted & Waiting for Result':'Waiting for Result',
  'Submitted & Accepted':'Accepted',
  'Submitted & Rejected':'Rejected'
};
function onStatusChange(){
  const statusRaw=document.getElementById('f-status').value;
  const isCompound=COMPOUND_STATUS_RESULT_MAP.hasOwnProperty(statusRaw);
  clearFieldError('fg-status');
  updateContractRequirement(isCompound?COMPOUND_STATUS_RESULT_MAP[statusRaw]:'');
}

function updateContractRequirement(result){
  const cLabel=document.getElementById('contract-label'),cGrp=document.getElementById('fg-contract'),cHint=document.getElementById('fh-contract');
  clearFieldError('fg-contract');
  if(result==='Accepted'){cLabel.innerHTML='Contract Signed <span class="req">*</span>';if(cGrp)cGrp.classList.add('result-required');if(cHint){cHint.classList.remove('error');cHint.classList.add('info');}}
  else{cLabel.innerHTML='Contract Signed';if(cGrp)cGrp.classList.remove('result-required');if(cHint)cHint.classList.remove('error','info');}
}

const RESPONSIBLE_NAMES=['Khairul','Masud','Amenul','Mokbul','Asifur','Aorchita','Farhana'];
const CUSTOM_RESPONSIBLE_KEY='bhumijo_custom_responsible_names';

function getCustomResponsibleNames(){
  try{ const v=JSON.parse(localStorage.getItem(CUSTOM_RESPONSIBLE_KEY)||'[]'); return Array.isArray(v)?v:[]; }
  catch(e){ return []; }
}
function saveCustomResponsibleNames(list){
  try{ localStorage.setItem(CUSTOM_RESPONSIBLE_KEY, JSON.stringify(list)); }catch(e){}
}
function renderResponsibleOptions(){
  const box=document.getElementById('responsible-options');
  if(!box)return;
  const all=RESPONSIBLE_NAMES.concat(getCustomResponsibleNames());
  box.innerHTML=all.map(n=>`<label class="multiselect-option"><input type="checkbox" value="${esc(n)}" onchange="toggleResponsibleName(this)"> ${esc(n)}</label>`).join('');
}
function addCustomResponsibleName(){
  const addInput=document.getElementById('responsible-add-input');
  if(!addInput)return;
  const name=(addInput.value||'').trim();
  addInput.value='';
  if(!name)return;
  const all=RESPONSIBLE_NAMES.concat(getCustomResponsibleNames());
  if(!all.some(n=>n.toLowerCase()===name.toLowerCase())){
    const custom=getCustomResponsibleNames();
    custom.push(name);
    saveCustomResponsibleNames(custom);
    renderResponsibleOptions();
  }
  const box=document.getElementById('responsible-options');
  const cb=box && Array.from(box.querySelectorAll('input[type=checkbox]')).find(c=>c.value.toLowerCase()===name.toLowerCase());
  if(cb){ cb.checked=true; toggleResponsibleName(cb); }
  addInput.focus();
}

function openResponsibleDropdown(){
  const panel=document.getElementById('responsible-panel');
  const input=document.getElementById('f-responsible');
  if(!panel||!input)return;
  const current=input.value||'';
  const parts=current.split(/,|&| and /i).map(s=>s.trim()).filter(Boolean);
  panel.querySelectorAll('input[type=checkbox]').forEach(cb=>{
    cb.checked=parts.some(p=>p.toLowerCase()===cb.value.toLowerCase());
  });
  panel.classList.add('open');
}
function closeResponsibleDropdown(){
  const panel=document.getElementById('responsible-panel');
  if(panel)panel.classList.remove('open');
}
function toggleResponsibleName(cb){
  const input=document.getElementById('f-responsible');
  if(!input)return;
  let parts=(input.value||'').split(',').map(s=>s.trim()).filter(Boolean);
  if(cb.checked){
    if(!parts.some(p=>p.toLowerCase()===cb.value.toLowerCase()))parts.push(cb.value);
  } else {
    parts=parts.filter(p=>p.toLowerCase()!==cb.value.toLowerCase());
  }
  input.value=parts.join(', ');
  clearFieldError('fg-responsible');
}
document.addEventListener('click', function(e){
  const wrap=document.getElementById('responsible-wrap');
  if(wrap && !wrap.contains(e.target)) closeResponsibleDropdown();
});

const CATEGORY_OPTIONS=[
  {value:'Proposal',label:'Proposal'},
  {value:'Presentation',label:'Presentation'},
  {value:'EOI -> RFP',label:'EOI → RFP'},
  {value:'EOI -> RFP -> Presentation',label:'EOI → RFP → Presentation'},
  {value:'Meeting',label:'Meeting / Initial Discussion'},
  {value:'General',label:'General'},
  {value:'Adhoc',label:'Adhoc'},
  {value:'Consultancy',label:'Consultancy'},
  {value:'Financial',label:'Financial'}
];
const CUSTOM_CATEGORY_KEY='bhumijo_custom_category_names';

function getCustomCategoryNames(){
  try{ const v=JSON.parse(localStorage.getItem(CUSTOM_CATEGORY_KEY)||'[]'); return Array.isArray(v)?v:[]; }
  catch(e){ return []; }
}
function saveCustomCategoryNames(list){
  try{ localStorage.setItem(CUSTOM_CATEGORY_KEY, JSON.stringify(list)); }catch(e){}
}
function renderCategoryOptions(){
  const box=document.getElementById('category-options');
  if(!box)return;
  const custom=getCustomCategoryNames().map(n=>({value:n,label:n}));
  const all=CATEGORY_OPTIONS.concat(custom);
  box.innerHTML=all.map(o=>`<label class="multiselect-option"><input type="checkbox" value="${esc(o.value)}" onchange="toggleCategoryName(this)"> ${esc(o.label)}</label>`).join('');
}
function addCustomCategoryName(){
  const addInput=document.getElementById('category-add-input');
  if(!addInput)return;
  const name=(addInput.value||'').trim();
  addInput.value='';
  if(!name)return;
  const all=CATEGORY_OPTIONS.map(o=>o.value).concat(getCustomCategoryNames());
  if(!all.some(n=>n.toLowerCase()===name.toLowerCase())){
    const custom=getCustomCategoryNames();
    custom.push(name);
    saveCustomCategoryNames(custom);
    renderCategoryOptions();
  }
  const box=document.getElementById('category-options');
  const cb=box && Array.from(box.querySelectorAll('input[type=checkbox]')).find(c=>c.value.toLowerCase()===name.toLowerCase());
  if(cb){ cb.checked=true; toggleCategoryName(cb); }
  addInput.focus();
}
function openCategoryDropdown(){
  const panel=document.getElementById('category-panel');
  const input=document.getElementById('f-category');
  if(!panel||!input)return;
  const current=input.value||'';
  const parts=current.split(',').map(s=>s.trim()).filter(Boolean);
  panel.querySelectorAll('input[type=checkbox]').forEach(cb=>{
    cb.checked=parts.some(p=>p.toLowerCase()===cb.value.toLowerCase());
  });
  panel.classList.add('open');
}
function closeCategoryDropdown(){
  const panel=document.getElementById('category-panel');
  if(panel)panel.classList.remove('open');
}
function toggleCategoryName(cb){
  const input=document.getElementById('f-category');
  if(!input)return;
  let parts=(input.value||'').split(',').map(s=>s.trim()).filter(Boolean);
  if(cb.checked){
    if(!parts.some(p=>p.toLowerCase()===cb.value.toLowerCase()))parts.push(cb.value);
  } else {
    parts=parts.filter(p=>p.toLowerCase()!==cb.value.toLowerCase());
  }
  input.value=parts.join(', ');
  clearFieldError('fg-category');
}
document.addEventListener('click', function(e){
  const wrap=document.getElementById('category-wrap');
  if(wrap && !wrap.contains(e.target)) closeCategoryDropdown();
});

function clearForm(){
  ['f-title','f-client','f-value','f-responsible','f-fileLoc','f-openDate','f-closeDate','f-startDate','f-endDate','f-remark'].forEach(id=>{document.getElementById(id).value='';});
  document.getElementById('f-entity').value='';document.getElementById('f-category').value='';document.getElementById('f-status').value='';document.getElementById('f-contract').value='';
  ['fg-title','fg-entity','fg-category','fg-client','fg-responsible','fg-openDate','fg-closeDate','fg-status','fg-contract','fg-remark'].forEach(id=>clearFieldError(id));
  const cl=document.getElementById('contract-label');if(cl)cl.innerHTML='Contract Signed';
  ['fg-contract'].forEach(id=>{const g=document.getElementById(id);if(g)g.classList.remove('result-required');});
  document.getElementById('upload-status').textContent='';
  document.getElementById('doc-upload').value='';
}

function saveProposal(){
  const title=(document.getElementById('f-title').value||'').trim();
  const entity=document.getElementById('f-entity').value;
  const category=document.getElementById('f-category').value;
  const client=(document.getElementById('f-client').value||'').trim();
  const responsible=(document.getElementById('f-responsible').value||'').trim();
  const fileLoc=(document.getElementById('f-fileLoc').value||'').trim();
  const openDate=document.getElementById('f-openDate').value;
  const closeDate=document.getElementById('f-closeDate').value;
  let status=document.getElementById('f-status').value;
  let result='';
  if(COMPOUND_STATUS_RESULT_MAP.hasOwnProperty(status)){
    result=COMPOUND_STATUS_RESULT_MAP[status];
    status='Submitted';
  } else if(editingId){
    result=(proposals.find(x=>x.id===editingId)||{}).result||'';
  }
  const contract=document.getElementById('f-contract').value;
  const remark=(document.getElementById('f-remark').value||'').trim();
  const value=document.getElementById('f-value').value.trim();
  const startDate=document.getElementById('f-startDate').value;
  const endDate=document.getElementById('f-endDate').value;
  const errors=[];
  if(!title)  {setFieldError('fg-title','fh-title');errors.push('Title');}
  if(!entity) {setFieldError('fg-entity','fh-entity');errors.push('Entity');}
  if(!category){setFieldError('fg-category','fh-category');errors.push('Category');}
  if(!client) {setFieldError('fg-client','fh-client');errors.push('Client');}
  if(!responsible){setFieldError('fg-responsible','fh-responsible');errors.push('Responsible Person');}
  if(!openDate){setFieldError('fg-openDate','fh-openDate');errors.push('Opening Date');}
  if(!closeDate){setFieldError('fg-closeDate','fh-closeDate');errors.push('Closing Date');}
  if(!status) {setFieldError('fg-status','fh-status');errors.push('Submission Status');}
  if(!remark) {setFieldError('fg-remark','fh-remark');errors.push('Remarks');}
  if(result==='Accepted'&&!contract){setFieldError('fg-contract','fh-contract');errors.push('Contract Signed');}
  if(errors.length){toast(`Required: ${errors.slice(0,3).join(', ')}${errors.length>3?' + '+(errors.length-3)+' more':''}`,'error');const f=document.querySelector('#proposal-modal .field-error');if(f)f.scrollIntoView({behavior:'smooth',block:'center'});return;}
  const p={id:editingId||'p_'+Date.now(),title,entity,category,client,value,responsible,fileLoc,openDate,closeDate,status,result,contract,startDate,endDate,remark,
    createdAt:editingId?(proposals.find(x=>x.id===editingId)||{}).createdAt:new Date().toISOString().substring(0,10)};
  if(editingId){proposals[proposals.findIndex(x=>x.id===editingId)]=p;toast('Proposal updated','success');}
  else{proposals.unshift(p);toast('Proposal added','success');}
  // Auto-add to clients if Accepted
  if(result==='Accepted'&&client){
    const exists=clients.find(c=>c.fromProposalId===p.id);
    if(!exists){
      clients.unshift({id:'c_'+Date.now(),name:client,entity,project:title,value,responsible,startDate,endDate,notes:remark.split('|')[0].trim().substring(0,200),fromProposalId:p.id,createdAt:p.createdAt});
      saveClients();
    }
  }
  saveData();closeModal();renderDashboard();filterTable();
}

// ─── DELETE ───────────────────────────────────────────────────────────────────
function confirmDelete(id){const p=proposals.find(x=>x.id===id);document.getElementById('confirm-msg').textContent=`Delete "${(p?.title||'').substring(0,55)}"? Cannot be undone.`;document.getElementById('confirm-ok-btn').onclick=()=>{deleteProposal(id);closeConfirm();};document.getElementById('confirm-overlay').classList.add('open');}
function closeConfirm(){document.getElementById('confirm-overlay').classList.remove('open');}
function deleteProposal(id){
  if (serverConnected) {
    deleteProposalOnServer(id).then(function(res){
      if (res && res.deleted) {
        proposals = proposals.filter(x => x.id !== id);
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify(proposals)); } catch(e){}
        closeDrawer(); renderDashboard(); filterTable();
        toast('Deleted', 'success');
      } else if (res && res.error === 'forbidden') {
        toast('Only the server PC can delete a proposal — ask whoever is at the main PC to delete it there.', 'error');
      } else {
        toast('Delete failed', 'error');
      }
    }).catch(function(){
      toast('Could not reach server to delete — try again once connected', 'error');
    });
  } else {
    proposals=proposals.filter(x=>x.id!==id);saveData();closeDrawer();renderDashboard();filterTable();toast('Deleted','success');
  }
}

// ─── EXPORT ───────────────────────────────────────────────────────────────────
function exportCSV(){
  const fields=['entity','title','category','client','value','openDate','closeDate','status','result','responsible','contract','startDate','endDate','remark','createdAt'];
  const header=['Entity','Title','Category','Client','Value','Opening Date','Closing Date','Status','Result','Responsible','Contract','Start Date','End Date','Remarks','Added On'];
  const rows=[header,...proposals.map(p=>fields.map(f=>'"'+((p[f]||'').toString()).replace(/"/g,'""')+'"'))];
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([rows.map(r=>r.join(',')).join('\n')],{type:'text/csv'}));a.download='Bhumijo_Proposals_'+new Date().toISOString().substring(0,10)+'.csv';a.click();toast('CSV downloaded','success');}

// ─── REPORTS ───────────────────────────────────────────────────────────────────
