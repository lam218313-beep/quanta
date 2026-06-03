import { useEffect, useState, useRef } from 'react'
import { Activity, Database, CheckCircle, RefreshCcw, Search, BarChart3, UploadCloud, Terminal, Download } from 'lucide-react'
import { supabase } from './supabaseClient'
import './App.css'

const PHASES = [
  { id: 'preliminar', label: 'Preliminar Simple', icon: Database },
  { id: 'descargados', label: 'Comprobantes Descargados', icon: CheckCircle },
  { id: 'enriquecimiento1', label: 'Enriquecimiento 1 (XML)', icon: Search },
  { id: 'enriquecimiento2', label: 'Enriquecimiento 2 (Contable)', icon: BarChart3 }
]

const generatePeriods = () => {
  const periods = []
  for (let year = 2025; year <= 2026; year++) {
    for (let month = 1; month <= 12; month++) {
      const mm = month < 10 ? `0${month}` : `${month}`
      periods.push(`${year}${mm}`)
    }
  }
  return periods.reverse()
}
const STATIC_PERIODS = generatePeriods()

const formatPeriod = (periodStr) => {
  if (!periodStr || periodStr.length !== 6) return periodStr;
  const year = periodStr.substring(0, 4);
  const monthNum = parseInt(periodStr.substring(4, 6), 10);
  const months = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
  return `${months[monthNum - 1]} ${year}`;
}

const API_BASE_URL = 'http://localhost:8000'

function App() {
  const [clientes, setClientes] = useState([])
  const [selectedCliente, setSelectedCliente] = useState('')
  const [selectedPeriodo, setSelectedPeriodo] = useState('')
  const [selectedPhase, setSelectedPhase] = useState('preliminar')
  
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState({ totalVentas: 0, totalCompras: 0, validos: 0, pendientes: 0 })
  const [data, setData] = useState([])
  const [notification, setNotification] = useState('')
  const [editingClient, setEditingClient] = useState(null)
  
  // Terminal state
  const [activeTaskId, setActiveTaskId] = useState('')
  const [terminalLogs, setTerminalLogs] = useState('')
  const terminalRef = useRef(null)

  // Simple Pagination state
  const [itemsToShow, setItemsToShow] = useState(50)

  useEffect(() => {
    async function loadContext() {
      const { data: clientsData } = await supabase.from('clientes').select('*')
      if (clientsData) setClientes(clientsData)
    }
    loadContext()
  }, [])

  useEffect(() => {
    if (selectedCliente) {
      const client = clientes.find(c => c.id === selectedCliente)
      setEditingClient(client ? { ...client } : null)
    } else {
      setEditingClient(null)
    }
  }, [selectedCliente, clientes])

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [terminalLogs])

  useEffect(() => {
    let interval = null;
    if (activeTaskId) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/api/bot/logs/${activeTaskId}`)
          if (res.ok) {
            const data = await res.json()
            setTerminalLogs(data.logs)
            if (!data.is_running && data.logs !== "No logs available yet...") {
              setTimeout(() => setActiveTaskId(''), 2000)
            }
          }
        } catch(e) {
          console.error("Error fetching logs", e)
        }
      }, 1000)
    }
    return () => { if (interval) clearInterval(interval) }
  }, [activeTaskId])

  const handleSaveClient = async () => {
    if (!editingClient) return
    setNotification('Guardando credenciales...')
    
    const { error } = await supabase
      .from('clientes')
      .update({
        usuario_sol: editingClient.usuario_sol,
        clave_sol: editingClient.clave_sol,
        client_id_api: editingClient.client_id_api,
        client_secret_api: editingClient.client_secret_api
      })
      .eq('id', editingClient.id)

    if (error) {
      setNotification(`❌ Error al guardar: ${error.message}`)
    } else {
      setNotification('✅ Credenciales guardadas correctamente')
      setClientes(clientes.map(c => c.id === editingClient.id ? editingClient : c))
    }
    setTimeout(() => setNotification(''), 3000)
  }

  const fetchTableData = async () => {
    if (!selectedCliente || !selectedPeriodo) return;
    setLoading(true)
    setItemsToShow(50) // Reset items
    try {
      const c_id = selectedCliente;
      if (selectedPhase === 'preliminar' || selectedPhase === 'enriquecimiento1' || selectedPhase === 'enriquecimiento2') {
        const { data: ventas } = await supabase
          .from('sire_preliminar_ventas')
          .select('id, cliente_id, serie_cdp, nro_cp, fecha_emision, razon_social, total_cp, igv_ipm, bi_gravada, estado_enriquecimiento, cuenta_contable, descripcion_cuenta, categoria, descripcion_comprobante')
          .eq('cliente_id', c_id)
          .eq('periodo', selectedPeriodo)
          
        const { data: compras } = await supabase
          .from('sire_preliminar_compras')
          .select('id, cliente_id, serie_cdp, nro_cp, fecha_emision, razon_social, total_cp, igv_ipm_dg, bi_gravado_dg, detraccion, estado_enriquecimiento, cuenta_contable, descripcion_cuenta, categoria, descripcion_comprobante')
          .eq('cliente_id', c_id)
          .eq('periodo', selectedPeriodo)

        const allE = [...(ventas || []).map(v => ({...v, tipo: 'VENTA'})), ...(compras || []).map(c => ({...c, tipo: 'COMPRA'}))]

        if (selectedPhase === 'preliminar') {
          setStats({
            totalVentas: ventas?.length || 0,
            totalCompras: compras?.length || 0,
            validos: allE.length,
            pendientes: 0
          })
          setData(allE)
        } else if (selectedPhase === 'enriquecimiento1') {
          const complete = allE.filter(x => x.estado_enriquecimiento === 'COMPLETO')
          const error = allE.filter(x => x.estado_enriquecimiento === 'ERROR')
          const pending = allE.filter(x => !x.estado_enriquecimiento)

          setStats({
            totalVentas: ventas?.length || 0,
            totalCompras: compras?.length || 0,
            validos: complete.length,
            pendientes: pending.length + error.length
          })
          setData(allE)
        } else if (selectedPhase === 'enriquecimiento2') {
          const classified = allE.filter(x => x.cuenta_contable)
          const unclassified = allE.filter(x => !x.cuenta_contable && x.estado_enriquecimiento === 'COMPLETO')

          setStats({
            totalVentas: ventas?.length || 0,
            totalCompras: compras?.length || 0,
            validos: classified.length,
            pendientes: unclassified.length
          })
          setData(allE.filter(x => x.estado_enriquecimiento === 'COMPLETO'))
        }
        
      } else if (selectedPhase === 'descargados') {
        const { data: fisicos } = await supabase
          .from('sire_comprobantes_fisicos')
          .select('*')
          .eq('cliente_id', selectedCliente)
          .eq('periodo', selectedPeriodo)
          
        const downloaded = fisicos?.filter(f => f.estado_xml === 'DESCARGADO') || []
        const pending = fisicos?.filter(f => f.estado_xml === 'PENDIENTE') || []
        const sales = fisicos?.filter(f => f.tipo_libro === 'VENTAS') || []
        const purchases = fisicos?.filter(f => f.tipo_libro === 'COMPRAS') || []

        setStats({
          totalVentas: sales.length,
          totalCompras: purchases.length,
          validos: downloaded.length,
          pendientes: pending.length
        })
        
        setData(fisicos || [])
      }
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTableData()
  }, [selectedCliente, selectedPeriodo, selectedPhase])

  const handleResetBots = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/bot/reset`, { method: 'POST' })
      const result = await response.json()
      setNotification(`🔄 ${result.message}`)
      setActiveTaskId(null)
      setTerminalLogs('')
      setTimeout(() => setNotification(''), 4000)
    } catch (e) {
      setNotification('❌ Error conectando con el servidor')
    }
  }

  const handleBotAction = async (action) => {
    const cliente = clientes.find(c => c.id === selectedCliente)
    if (!cliente) return
    
    setNotification(`Enviando orden de ejecución al bot...`)
    setTerminalLogs('Iniciando tarea...\n')
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/bot/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ruc: cliente.ruc, periodo: selectedPeriodo })
      })
      const result = await response.json()
      
      if (response.ok) {
        setNotification(`✅ ${result.message}`)
        if (result.task_id) {
          setActiveTaskId(result.task_id)
        }
      } else {
        setNotification(`❌ Error: ${result.detail || 'Error en el servidor'}`)
        setTerminalLogs(`Error de API: ${result.detail || 'Desconocido'}\n`)
      }
      
      setTimeout(() => setNotification(''), 5000)
    } catch (e) {
      setNotification(`❌ Error de conexión con FastAPI en el puerto 8000. ¿Está corriendo uvicorn?`)
      setTerminalLogs(`Error de conexión al puerto 8000.\n`)
      setTimeout(() => setNotification(''), 5000)
    }
  }

  const handleExportPdfs = async (tipo_libro, allow_incomplete = false) => {
    const cliente = clientes.find(c => c.id === selectedCliente)
    if (!cliente) return
    
    setNotification(`Generando PDF consolidado de ${tipo_libro}...`)
    try {
      const response = await fetch(`${API_BASE_URL}/api/export/pdf-merged`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ruc: cliente.ruc, periodo: selectedPeriodo, tipo_libro, allow_incomplete })
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        setNotification(`❌ Error: ${errorData.detail || 'Error al generar PDF'}`)
        setTimeout(() => setNotification(''), 4000)
        return
      }
      
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `Comprobantes_${tipo_libro}_${selectedPeriodo}.pdf`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      setNotification(`✅ PDF consolidado de ${tipo_libro} descargado con éxito.`)
      setTimeout(() => setNotification(''), 4000)
    } catch (e) {
      setNotification(`❌ Error de conexión al exportar.`)
      setTimeout(() => setNotification(''), 4000)
    }
  }

  return (
    <div className="app-container">
      <header className="header animate-fade-in">
        <h1>Contax Dashboard</h1>
        <p>Monitor de Procesamiento SIRE en Tiempo Real</p>
      </header>

      {/* Selector de Contexto */}
      <div className="glass-panel controls-row animate-fade-in" style={{animationDelay: '0.1s'}}>
        <div className="control-group">
          <label>Cliente</label>
          <select value={selectedCliente} onChange={e => setSelectedCliente(e.target.value)}>
            <option value="">-- Seleccionar Cliente --</option>
            {clientes.map(c => (
              <option key={c.id} value={c.id}>{c.ruc} - {c.razon_social}</option>
            ))}
          </select>
        </div>
        <div className="control-group">
          <label>Periodo (Fijo)</label>
          <select value={selectedPeriodo} onChange={e => setSelectedPeriodo(e.target.value)}>
            <option value="">-- Seleccionar Periodo --</option>
            {STATIC_PERIODS.map(p => (
              <option key={p} value={p}>{formatPeriod(p)}</option>
            ))}
          </select>
        </div>
        <div className="control-group" style={{justifyContent: 'flex-end', flex: 0.2}}>
          <button onClick={async () => {
            setNotification('Sincronizando archivos físicos con DB...')
            try { await fetch(`${API_BASE_URL}/api/bot/sync-files`) } catch(e) {}
            await fetchTableData()
            setNotification('✅ Datos recargados')
            setTimeout(() => setNotification(''), 3000)
          }} title="Recargar Datos" className="bot-btn secondary"><RefreshCcw size={20}/></button>
        </div>
      </div>

      {/* Credenciales Rápidas (Debug) */}
      {editingClient && (
        <div className="glass-panel animate-fade-in" style={{animationDelay: '0.12s', marginBottom: '2rem', padding: '1.5rem', borderLeft: '4px solid #8b5cf6'}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem'}}>
            <h3 style={{margin: 0, color: 'var(--text-color)', fontSize: '1rem'}}>🛠️ Debug: Credenciales del Cliente</h3>
            <button onClick={handleSaveClient} className="bot-btn primary" style={{padding: '0.4rem 1rem', fontSize: '0.85rem', background: '#8b5cf6'}}>Guardar Cambios</button>
          </div>
          <div style={{display: 'flex', gap: '1rem', flexWrap: 'wrap'}}>
            <div className="control-group" style={{flex: '1 1 150px'}}>
              <label>RUC (Solo lectura)</label>
              <input type="text" value={editingClient.ruc} disabled style={{background: 'rgba(0,0,0,0.2)', color: '#888'}} />
            </div>
            <div className="control-group" style={{flex: '1 1 150px'}}>
              <label>Usuario SOL</label>
              <input type="text" value={editingClient.usuario_sol || ''} onChange={e => setEditingClient({...editingClient, usuario_sol: e.target.value})} />
            </div>
            <div className="control-group" style={{flex: '1 1 150px'}}>
              <label>Clave SOL</label>
              <input type="text" value={editingClient.clave_sol || ''} onChange={e => setEditingClient({...editingClient, clave_sol: e.target.value})} />
            </div>
            <div className="control-group" style={{flex: '1 1 200px'}}>
              <label>Client ID (API)</label>
              <input type="text" value={editingClient.client_id_api || ''} onChange={e => setEditingClient({...editingClient, client_id_api: e.target.value})} />
            </div>
            <div className="control-group" style={{flex: '1 1 200px'}}>
              <label>Client Secret (API)</label>
              <input type="text" value={editingClient.client_secret_api || ''} onChange={e => setEditingClient({...editingClient, client_secret_api: e.target.value})} />
            </div>
          </div>
        </div>
      )}

      {/* Bot Actions */}
      <div className="glass-panel animate-fade-in" style={{animationDelay: '0.15s', marginBottom: '2rem', padding: '1.5rem'}}>
        <h3 style={{margin: '0 0 1rem 0', color: 'var(--text-color)', fontSize: '1.1rem'}}>🤖 Control de Bots (Ejecución Directa)</h3>
        <div style={{display: 'flex', gap: '0.5rem', flexWrap: 'wrap'}}>
          <button disabled={!selectedCliente || !selectedPeriodo} onClick={() => handleBotAction('download-api')} className="bot-btn primary">
            <UploadCloud size={16}/> 1. Propuesta SIRE API
          </button>
          <button disabled={!selectedCliente} onClick={() => handleBotAction('automation-login')} className="bot-btn secondary">
            <Activity size={16}/> 2. Generar Credenciales
          </button>
          <button disabled={!selectedCliente} onClick={() => handleBotAction('download-fisicos')} className="bot-btn secondary">
            <Database size={16}/> 3. Descargar XML Físicos
          </button>
          <button disabled={!selectedCliente} onClick={() => handleBotAction('enrich-xml')} className="bot-btn primary" style={{background: 'var(--accent-hover)'}}>
            <Search size={16}/> 4. Extraer Detalles XML
          </button>
          <button disabled={!selectedCliente} onClick={() => handleBotAction('classify-ai')} className="bot-btn" style={{background: '#8b5cf6', color: 'white'}}>
            <BarChart3 size={16}/> 5. Clasificar con IA
          </button>
          <button onClick={async () => {
            setNotification('🔄 Sincronizando archivos físicos con base de datos...')
            try {
              const res = await fetch(`${API_BASE_URL}/api/bot/sync-files`, { method: 'POST' })
              const r = await res.json()
              setNotification(`✅ ${r.message}`)
              setTimeout(() => setNotification(''), 5000)
            } catch(e) { setNotification('❌ Error al sincronizar') }
          }} className="bot-btn" style={{background: '#0ea5e9', color: 'white'}} title="Escanea carpetas locales y actualiza Supabase con los archivos que realmente existen">
            🔁 Sincronizar Archivos
          </button>
          <button onClick={handleResetBots} className="bot-btn" style={{background: '#ef4444', color: 'white', marginLeft: 'auto'}} title="Libera bots bloqueados. Úsalo si ves 'already running' pero no pasa nada.">
            ⚠️ Reset Bots
          </button>
        </div>
        {notification && <div className="notification">{notification}</div>}

        {/* Console Window */}
        {(activeTaskId || terminalLogs) && (
          <div className="terminal-window animate-fade-in" style={{marginTop: '1rem'}}>
            <div className="terminal-header">
              <span style={{display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
                <Terminal size={14} /> Terminal: {activeTaskId || 'Finalizado'}
              </span>
              {activeTaskId && <Activity size={14} className="animate-pulse" style={{color: '#10b981'}} />}
            </div>
            <pre className="terminal-content" ref={terminalRef}>
              {terminalLogs}
            </pre>
          </div>
        )}
      </div>

      {/* Pestañas de Fases */}
      <div className="phases-container animate-fade-in" style={{animationDelay: '0.2s'}}>
        {PHASES.map(phase => {
          const Icon = phase.icon
          return (
            <button 
              key={phase.id} 
              className={`phase-btn ${selectedPhase === phase.id ? 'active' : ''}`}
              onClick={() => setSelectedPhase(phase.id)}
            >
              <div style={{display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
                <Icon size={18} />
                {phase.label}
              </div>
            </button>
          )
        })}
      </div>

      {/* Panel de Estadísticas */}
      {selectedCliente && selectedPeriodo && (
        <>
          <div className="stats-grid animate-fade-in" style={{animationDelay: '0.3s'}}>
            <div className="glass-panel stat-card">
              <div className="stat-title">Total Comprobantes (Ventas)</div>
              <div className="stat-value">{stats.totalVentas}</div>
              <div className="stat-desc">En este periodo</div>
            </div>
            <div className="glass-panel stat-card">
              <div className="stat-title">Total Comprobantes (Compras)</div>
              <div className="stat-value">{stats.totalCompras}</div>
              <div className="stat-desc">En este periodo</div>
            </div>
            
            {selectedPhase === 'descargados' && (
              <>
                <div className="glass-panel stat-card">
                  <div className="stat-title">Descargados Exitosamente</div>
                  <div className="stat-value" style={{color: '#4ade80'}}>{stats.validos}</div>
                  <div className="stat-desc">XML & PDF guardados</div>
                </div>
                <div className="glass-panel stat-card">
                  <div className="stat-title">En Cola / Pendientes</div>
                  <div className="stat-value" style={{color: '#facc15'}}>{stats.pendientes}</div>
                  <div className="stat-desc">Esperando descarga</div>
                </div>
              </>
            )}
            
            {selectedPhase === 'enriquecimiento1' && (
              <>
                <div className="glass-panel stat-card">
                  <div className="stat-title">Glosa Extraída</div>
                  <div className="stat-value" style={{color: '#4ade80'}}>{stats.validos}</div>
                  <div className="stat-desc">XML parseado con éxito</div>
                </div>
                <div className="glass-panel stat-card">
                  <div className="stat-title">Por Extraer / Error</div>
                  <div className="stat-value" style={{color: '#facc15'}}>{stats.pendientes}</div>
                  <div className="stat-desc">Falta leer XML</div>
                </div>
              </>
            )}

            {selectedPhase === 'enriquecimiento2' && (
              <>
                <div className="glass-panel stat-card">
                  <div className="stat-title">Clasificados por IA</div>
                  <div className="stat-value" style={{color: '#8b5cf6'}}>{stats.validos}</div>
                  <div className="stat-desc">Cuenta PCGE asignada</div>
                </div>
                <div className="glass-panel stat-card">
                  <div className="stat-title">Por Clasificar</div>
                  <div className="stat-value" style={{color: '#facc15'}}>{stats.pendientes}</div>
                  <div className="stat-desc">Esperando a la IA</div>
                </div>
              </>
            )}
            
            {selectedPhase === 'preliminar' && (
              <div className="glass-panel stat-card" style={{gridColumn: 'span 2'}}>
                <div className="stat-title">Total Preliminares</div>
                <div className="stat-value">{stats.validos}</div>
                <div className="stat-desc">Extraídos de TXT</div>
              </div>
            )}
          </div>

          {/* Acciones Adicionales */}
          {selectedPhase === 'descargados' && (
            <div className="glass-panel animate-fade-in" style={{marginBottom: '1rem', padding: '1rem', display: 'flex', gap: '1rem', justifyContent: 'flex-end', animationDelay: '0.35s', flexWrap: 'wrap'}}>
              <button onClick={() => handleExportPdfs('COMPRAS', false)} className="bot-btn primary" style={{fontSize: '0.85rem', padding: '0.5rem 1rem', background: '#3b82f6'}}>
                <Download size={14}/> Consolidar Compras (Estricto)
              </button>
              <button onClick={() => handleExportPdfs('COMPRAS', true)} className="bot-btn secondary" style={{fontSize: '0.85rem', padding: '0.5rem 1rem'}}>
                <Download size={14}/> Consolidar Compras (Incompleto)
              </button>
              <button onClick={() => handleExportPdfs('VENTAS', false)} className="bot-btn primary" style={{fontSize: '0.85rem', padding: '0.5rem 1rem', background: '#3b82f6'}}>
                <Download size={14}/> Consolidar Ventas (Estricto)
              </button>
              <button onClick={() => handleExportPdfs('VENTAS', true)} className="bot-btn secondary" style={{fontSize: '0.85rem', padding: '0.5rem 1rem'}}>
                <Download size={14}/> Consolidar Ventas (Incompleto)
              </button>
            </div>
          )}

          {/* Data Table */}
          <div className="glass-panel animate-fade-in" style={{animationDelay: '0.4s'}}>
            <div className="data-table-container" style={{maxHeight: '500px', overflowY: 'auto'}}>
              {loading ? (
                <div style={{textAlign: 'center', padding: '3rem', color: 'var(--text-muted)'}}>
                  <RefreshCcw className="animate-spin" size={32} style={{margin: '0 auto 1rem'}} />
                  Cargando datos...
                </div>
              ) : data.length > 0 ? (
                <table style={{width: '100%'}}>
                  <thead style={{position: 'sticky', top: 0, zIndex: 10, background: '#0f172a'}}>
                    <tr>
                      <th>Tipo</th>
                      <th>Serie-Número</th>
                      <th>Fecha</th>
                      <th>RUC Tercero</th>
                      
                      {selectedPhase === 'descargados' && <th>Estado XML</th>}
                      
                      {selectedPhase === 'enriquecimiento1' && (
                        <>
                          <th>Estado Extracción</th>
                          <th>Descripción (Glosa)</th>
                        </>
                      )}
                      
                      {selectedPhase === 'enriquecimiento2' && (
                        <>
                          <th style={{width: '25%'}}>Glosa Extraída</th>
                          <th style={{width: '10%'}}>Base Imp.</th>
                          <th style={{width: '10%'}}>IGV</th>
                          <th style={{width: '15%'}}>Categoría</th>
                          <th style={{width: '15%'}}>Cuenta Contable</th>
                        </>
                      )}
                      
                      <th>Monto Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.slice(0, itemsToShow).map((row, i) => (
                      <tr key={i}>
                        <td>
                          <span className={`status-badge ${row.tipo === 'VENTA' || row.tipo_libro === 'VENTAS' ? 'status-success' : 'status-pending'}`}>
                            {row.tipo || row.tipo_libro}
                          </span>
                        </td>
                        <td>{row.serie_cdp || row.serie}-{row.nro_cp || row.numero}</td>
                        <td>{row.fecha_emision || '-'}</td>
                        <td>{row.nro_doc_identidad || row.ruc_tercero}</td>
                        
                        {selectedPhase === 'descargados' && (
                          <td>
                            <span className={`status-badge ${row.estado_xml === 'DESCARGADO' ? 'status-success' : row.estado_xml === 'PENDIENTE' ? 'status-pending' : 'status-error'}`}>
                              {row.estado_xml}
                            </span>
                          </td>
                        )}

                        {selectedPhase === 'enriquecimiento1' && (
                          <>
                            <td>
                              <span className={`status-badge ${row.estado_enriquecimiento === 'COMPLETO' ? 'status-success' : row.estado_enriquecimiento === 'ERROR' ? 'status-error' : 'status-pending'}`}>
                                {row.estado_enriquecimiento || 'PENDIENTE'}
                              </span>
                            </td>
                            <td style={{maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}} title={row.descripcion_comprobante}>
                              {row.descripcion_comprobante || '-'}
                            </td>
                          </>
                        )}

                        {selectedPhase === 'enriquecimiento2' && (
                          <>
                            <td className="truncate-cell" title={row.descripcion_comprobante}>
                              <div style={{fontSize: '0.85rem', color: 'var(--text-color)', opacity: 0.9}}>
                                {row.descripcion_comprobante || 'Sin descripción'}
                              </div>
                            </td>
                            <td>S/ {Number(row.bi_gravado_dg || row.bi_gravada || 0).toFixed(2)}</td>
                            <td>S/ {Number(row.igv_ipm_dg || row.igv_ipm || 0).toFixed(2)}</td>
                            <td>
                              <span className={`status-badge ${row.categoria ? 'status-success' : 'status-pending'}`} style={row.categoria ? {background: 'rgba(139, 92, 246, 0.2)', color: '#a78bfa'} : {}}>
                                {row.categoria || 'Pendiente'}
                              </span>
                            </td>
                            <td>
                              {row.cuenta_contable ? (
                                <div style={{display: 'flex', flexDirection: 'column', gap: '0.2rem'}}>
                                  <span style={{fontWeight: '600', color: '#a78bfa'}}>{row.cuenta_contable}</span>
                                  <span style={{fontSize: '0.75rem', opacity: 0.8}} title={row.descripcion_cuenta}>{row.descripcion_cuenta}</span>
                                </div>
                              ) : (
                                <span className="status-badge status-pending">Pendiente</span>
                              )}
                            </td>
                          </>
                        )}

                        <td>S/ {row.total_cp?.toFixed(2) || (row.monto_total || row.mto_imp_venta || 0).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div style={{textAlign: 'center', padding: '3rem', color: 'var(--text-muted)'}}>
                  No hay datos para esta fase.
                </div>
              )}
            </div>
            
            {/* Load More Button */}
            {data.length > itemsToShow && (
              <div style={{textAlign: 'center', padding: '1rem', borderTop: '1px solid rgba(255,255,255,0.05)'}}>
                <button 
                  onClick={() => setItemsToShow(prev => prev + 50)} 
                  className="bot-btn secondary"
                  style={{margin: '0 auto', fontSize: '0.85rem', padding: '0.4rem 1.2rem'}}
                >
                  Cargar 50 más (Mostrando {itemsToShow} de {data.length})
                </button>
              </div>
            )}
            {data.length > 0 && data.length <= itemsToShow && (
              <div style={{textAlign: 'center', padding: '1rem', color: '#64748b', fontSize: '0.85rem', borderTop: '1px solid rgba(255,255,255,0.05)'}}>
                Mostrando todos los {data.length} comprobantes.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

export default App
