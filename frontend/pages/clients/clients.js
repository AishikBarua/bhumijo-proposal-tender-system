/* The clients screen.
   Moved verbatim from Bhumijo_Proposal_Tracker_22Jul2026.html — 7 function(s), not rewritten.
   Loaded in a fixed order by index.html, sharing one scope, exactly as before. */

function renderClients() {
  const q=(document.getElementById('client-search').value||'').toLowerCase();
  const entity=document.getElementById('client-filter-entity').value;
  const grid=document.getElementById('client-grid');
  const filtered=clients.filter(c=>{
    if(entity&&c.entity!==entity)return false;
    if(q&&!(c.name||'').toLowerCase().includes(q)&&!(c.project||'').toLowerCase().includes(q))return false;
    return true;
  });
  if(!filtered.length){
    grid.innerHTML=`<div class="clients-empty" style="grid-column:1/-1"><div class="icon">◉</div><p>${clients.length===0?'No clients yet. Accept proposals to auto-generate records, or add manually.':'No clients match your search.'}</p></div>`;
    return;
  }
  const colMap={'P&D':'var(--pd)','FM':'var(--fm)','WASH':'var(--wash)','Tech':'var(--tech)'};
  grid.innerHTML=filtered.map(c=>`
    <div class="client-card">
      <div class="client-card-accent" style="background:${colMap[c.entity]||'var(--accent)'}"></div>
      <div class="client-actions">
        <button class="client-action-btn" onclick="event.stopPropagation();editClient('${c.id}')">✏</button>
        <button class="client-action-btn" onclick="event.stopPropagation();confirmDeleteClient('${c.id}')" style="color:var(--red)">✕</button>
      </div>
      <div class="client-name">${esc(c.name)}</div>
      <div class="client-project">${esc(c.project)}</div>
      <div class="client-meta">
        <span class="client-pill entity">${esc(c.entity)}</span>
        ${c.value?`<span class="client-pill value">Value: ${esc(c.value)}</span>`:''}
        ${c.startDate?`<span class="client-pill">Start: ${fmtDate(c.startDate)}</span>`:''}
        ${c.endDate?`<span class="client-pill">End: ${fmtDate(c.endDate)}</span>`:''}
        ${c.responsible?`<span class="client-pill">${esc(c.responsible)}</span>`:''}
      </div>
      ${c.notes?`<div style="font-size:11px;color:var(--text3);margin-top:8px;padding-left:10px;line-height:1.5">${esc(c.notes)}</div>`:''}
    </div>
  `).join('');
}

function openClientModal(id) {
  editingClientId = id||null;
  if(id) {
    const c=clients.find(x=>x.id===id);
    if(!c)return;
    document.getElementById('client-modal-title').textContent='Edit Client';
    document.getElementById('fc-name').value=c.name||'';
    document.getElementById('fc-entity').value=c.entity||'';
    document.getElementById('fc-project').value=c.project||'';
    document.getElementById('fc-value').value=c.value||'';
    document.getElementById('fc-responsible').value=c.responsible||'';
    document.getElementById('fc-startDate').value=c.startDate||'';
    document.getElementById('fc-endDate').value=c.endDate||'';
    document.getElementById('fc-notes').value=c.notes||'';
  } else {
    document.getElementById('client-modal-title').textContent='Add Client';
    ['fc-name','fc-project','fc-value','fc-responsible','fc-startDate','fc-endDate','fc-notes'].forEach(id=>document.getElementById(id).value='');
    document.getElementById('fc-entity').value='';
  }
  document.getElementById('client-modal').classList.add('open');
}
function closeClientModal(){document.getElementById('client-modal').classList.remove('open');editingClientId=null;}

function saveClient() {
  const name=document.getElementById('fc-name').value.trim();
  const entity=document.getElementById('fc-entity').value;
  const project=document.getElementById('fc-project').value.trim();
  if(!name){toast('Client name is required','error');return;}
  if(!entity){toast('Entity is required','error');return;}
  if(!project){toast('Project name is required','error');return;}
  const c={
    id: editingClientId||'c_'+Date.now(),
    name, entity, project,
    value: document.getElementById('fc-value').value.trim(),
    responsible: document.getElementById('fc-responsible').value.trim(),
    startDate: document.getElementById('fc-startDate').value,
    endDate: document.getElementById('fc-endDate').value,
    notes: document.getElementById('fc-notes').value.trim(),
    createdAt: editingClientId?(clients.find(x=>x.id===editingClientId)||{}).createdAt:new Date().toISOString().substring(0,10)
  };
  if(editingClientId){const idx=clients.findIndex(x=>x.id===editingClientId);clients[idx]=c;toast('Client updated','success');}
  else{clients.unshift(c);toast('Client added','success');}
  saveClients();
  closeClientModal();
  renderClients();
}

function editClient(id){openClientModal(id);}

function confirmDeleteClient(id) {
  const c=clients.find(x=>x.id===id);
  document.getElementById('confirm-msg').textContent=`Delete client "${(c?.name||'').substring(0,50)}"? This cannot be undone.`;
  document.getElementById('confirm-ok-btn').onclick=()=>{clients=clients.filter(x=>x.id!==id);saveClients();closeConfirm();renderClients();toast('Client deleted','success');};
  document.getElementById('confirm-overlay').classList.add('open');
}

function exportClientsCSV() {
  const fields=['name','entity','project','value','responsible','startDate','endDate','notes','createdAt'];
  const header=['Client Name','Entity','Project','Value','Responsible','Start Date','End Date','Notes','Added On'];
  const rows=[header,...clients.map(c=>fields.map(f=>'"'+((c[f]||'')).replace(/"/g,'""')+'"'))];
  const csv=rows.map(r=>r.join(',')).join('\n');
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));
  a.download='Bhumijo_Clients_'+new Date().toISOString().substring(0,10)+'.csv';
  a.click();
  toast('Clients CSV downloaded','success');
}

// ─── DRAWER ───────────────────────────────────────────────────────────────────
