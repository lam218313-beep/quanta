import { useEffect, useState, useRef } from 'react'
import { Activity, Database, CheckCircle, RefreshCcw, Search, BarChart3, UploadCloud, Terminal, Download, Edit2, X, Upload, ChevronRight, ChevronDown, ChevronUp, UserPlus, Settings, FileText, Calculator } from 'lucide-react'
import { supabase } from './supabaseClient'
import './App.css'
import FacturacionView from './components/FacturacionView'

const STEPS = [
  { id: 1, title: 'Sincronización SIRE', icon: Database, phaseFilter: 'descargados' },
  { id: 2, title: 'Procesamiento IA', icon: BarChart3, phaseFilter: 'enriquecimiento2' },
  { id: 3, title: 'Cierre y Exportación', icon: CheckCircle, phaseFilter: 'preliminar' }
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

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://quanta-production-07d7.up.railway.app'

function App() {
  const [clientes, setClientes] = useState([])
  const [selectedCliente, setSelectedCliente] = useState('')
  const [selectedPeriodo, setSelectedPeriodo] = useState('')
  const [activeStep, setActiveStep] = useState(1)
  const [activeMainTab, setActiveMainTab] = useState('contabilidad')
  
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState([])
  const [notifications, setNotifications] = useState([])
  const [clientSearchText, setClientSearchText] = useState('')
  const [showAddClientModal, setShowAddClientModal] = useState(false)
  const [showSettingsModal, setShowSettingsModal] = useState(false)
  const [editingClient, setEditingClient] = useState(null)
  const [newClient, setNewClient] = useState({ ruc: '', razon_social: '', usuario_sol: '', clave_sol: '', rubro: '', cuentas_contables: '' })

  // Terminal state
  const [activeTaskId, setActiveTaskId] = useState('')
  const [terminalLogs, setTerminalLogs] = useState('')
  const [isTerminalMinimized, setIsTerminalMinimized] = useState(false)
  const terminalRef = useRef(null)

  // Simple Pagination
  const [itemsToShow, setItemsToShow] = useState(50)

  const addToast = (msg, type = 'info') => {
    const id = Date.now()
    setNotifications(prev => [...prev, { id, msg, type }])
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id))
    }, 5000)
  }

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
      if (client) setClientSearchText(`${client.ruc} - ${client.razon_social}`)
    } else {
      setEditingClient(null)
      setClientSearchText('')
    }
  }, [selectedCliente, clientes])

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [terminalLogs])

  const fetchTableData = async () => {
    if (!selectedCliente || !selectedPeriodo) return;
    setLoading(true)
    setItemsToShow(50)
    try {
      const c_id = selectedCliente;
      const stepConfig = STEPS.find(s => s.id === activeStep)
      const selectedPhase = stepConfig.phaseFilter

      if (selectedPhase === 'preliminar' || selectedPhase === 'enriquecimiento2') {
        const { data: ventas } = await supabase
          .from('sire_preliminar_ventas')
          .select('*')
          .eq('cliente_id', c_id)
          .eq('periodo', selectedPeriodo)
          
        const { data: compras } = await supabase
          .from('sire_preliminar_compras')
          .select('*')
          .eq('cliente_id', c_id)
          .eq('periodo', selectedPeriodo)

        const allE = [...(ventas || []).map(v => ({...v, tipo: 'VENTA'})), ...(compras || []).map(c => ({...c, tipo: 'COMPRA'}))]

        if (selectedPhase === 'preliminar') {
          setData(allE)
        } else if (selectedPhase === 'enriquecimiento2') {
          setData(allE.filter(x => x.estado_enriquecimiento === 'COMPLETO'))
        }
        
      } else if (selectedPhase === 'descargados') {
        const { data: fisicos } = await supabase
          .from('sire_comprobantes_fisicos')
          .select('*, sire_preliminar_compras(fecha_emision, total_cp), sire_preliminar_ventas(fecha_emision, mto_imp_venta)')
          .eq('cliente_id', selectedCliente)
          .eq('periodo', selectedPeriodo)
          
        let localFiles = []
        try {
          const res = await fetch(`${API_BASE_URL}/api/bot/local-files`)
          if (res.ok) {
            const json = await res.json()
            localFiles = json.files || []
          }
        } catch(e) {}
        
        const enrichedFisicos = (fisicos || []).map(f => {
          const rucTercero = f.ruc_tercero || ''
          const tipoCp = f.tipo_cp || ''
          const baseName = `${rucTercero}-${tipoCp}-${f.serie || ''}-${f.numero || ''}`
          
          if (localFiles.includes(`${baseName}.xml`) || localFiles.includes(`${baseName}.zip`)) f.estado_xml = 'DESCARGADO'
          if (localFiles.includes(`${baseName}.pdf`)) f.estado_pdf = 'DESCARGADO'

          if (f.sire_preliminar_compras) {
            f.fecha_emision = f.sire_preliminar_compras.fecha_emision;
            f.total_cp = f.sire_preliminar_compras.total_cp;
          } else if (f.sire_preliminar_ventas) {
            f.fecha_emision = f.sire_preliminar_ventas.fecha_emision;
            f.total_cp = f.sire_preliminar_ventas.mto_imp_venta;
          }
          
          return f
        })
        setData(enrichedFisicos)
      }
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTableData()
  }, [selectedCliente, selectedPeriodo, activeStep])

  useEffect(() => {
    let interval = null;
    if (activeTaskId) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/api/bot/logs/${activeTaskId}`)
          if (res.ok) {
            const data = await res.json()
            setTerminalLogs(data.logs)
            if (data.is_running === false && data.logs !== "No logs available yet...") {
              fetchTableData(); // Refresh immediately
              setTimeout(() => {
                setActiveTaskId('')
                setIsTerminalMinimized(true)
              }, 2000)
            }
          }
        } catch(e) {
          console.error("Error fetching logs", e)
        }
      }, 1000)
    }
    return () => { if (interval) clearInterval(interval) }
  }, [activeTaskId, selectedCliente, selectedPeriodo, activeStep])

  useEffect(() => {
    let intervalId
    if (activeTaskId) {
      intervalId = setInterval(() => { fetchTableData() }, 5000)
    }
    return () => { if (intervalId) clearInterval(intervalId) }
  }, [activeTaskId, selectedCliente, selectedPeriodo, activeStep])

  const waitForTask = (taskId) => {
    return new Promise((resolve) => {
      const interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/api/bot/logs/${taskId}`)
          if (res.ok) {
            const data = await res.json()
            if (data.is_running === false) {
              clearInterval(interval)
              resolve(true)
            }
          }
        } catch(e) {
          clearInterval(interval)
          resolve(false)
        }
      }, 2000)
    })
  }

  const handleBotActionRaw = async (action, extraPayload = {}) => {
    const cliente = clientes.find(c => c.id === selectedCliente)
    if (!cliente) return {ok: false}
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/bot/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ruc: cliente.ruc, periodo: selectedPeriodo, ...extraPayload })
      })
      const result = await response.json()
      return {ok: response.ok, ...result}
    } catch (e) {
      return {ok: false, detail: 'Error de conexión'}
    }
  }

  const handleBotAction = async (action, extraPayload = {}) => {
    addToast(`Enviando orden de ejecución...`, 'info')
    setTerminalLogs('Iniciando tarea...\n')
    setIsTerminalMinimized(false)
    
    const result = await handleBotActionRaw(action, extraPayload)
    if (result.ok) {
      addToast(`✅ ${result.message}`, 'success')
      if (result.task_id) setActiveTaskId(result.task_id)
    } else {
      addToast(`❌ Error: ${result.detail || 'Error en el servidor'}`, 'danger')
      setTerminalLogs(`Error de API: ${result.detail || 'Desconocido'}\n`)
    }
  }

  const handleSyncSireFisicos = async () => {
    const cliente = clientes.find(c => c.id === selectedCliente)
    if (!cliente || !selectedPeriodo) return

    const hasCreds = cliente.client_id_api && cliente.client_secret_api
    
    if (!hasCreds) {
      addToast('Verificando credenciales mediante automatización...', 'info')
      setTerminalLogs('Generando credenciales API...\n')
      const loginRes = await handleBotActionRaw('automation-login')
      if (loginRes.ok) {
        if (loginRes.task_id) {
          setActiveTaskId(loginRes.task_id)
          await waitForTask(loginRes.task_id)
        }
      } else {
        addToast('❌ Error al generar credenciales', 'danger')
        return
      }
    }
    
    addToast('Iniciando descarga de comprobantes físicos...', 'info')
    handleBotAction('download-fisicos')
  }
  const handleResetPendientes = async () => {
    const cliente = clientes.find(c => c.id === selectedCliente)
    if (!cliente || !selectedPeriodo) return

    if (!window.confirm("¿Seguro que quieres pasar todos los comprobantes fallidos a PENDIENTE para que el bot los reintente?")) return;

    addToast('Reiniciando estado de comprobantes...', 'info')
    try {
      const response = await fetch(`${API_BASE_URL}/api/comprobantes/reset-pendientes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ruc: cliente.ruc, periodo: selectedPeriodo })
      })
      const result = await response.json()
      if (response.ok) {
        addToast(`✅ ${result.mensaje}`, 'success')
        fetchData() // Refresh table
      } else {
        addToast(`❌ Error: ${result.detail || 'Error en servidor'}`, 'danger')
      }
    } catch (e) {
      addToast(`Error de conexión`, 'danger')
    }
  }

  const handleManualUpload = async (comprobanteId, file, fileType) => {
    if (!file) return;
    const formData = new FormData()
    formData.append('file', file)
    formData.append('file_type', fileType)

    addToast(`Subiendo ${fileType.toUpperCase()}...`, 'info')
    try {
      const response = await fetch(`${API_BASE_URL}/api/comprobante/${comprobanteId}/upload`, {
        method: 'POST',
        body: formData
      })
      const result = await response.json()
      if (response.ok) {
        addToast(`✅ ${fileType.toUpperCase()} subido correctamente`, 'success')
        fetchData() // Refresh table
      } else {
        addToast(`❌ Error: ${result.detail || 'Error al subir archivo'}`, 'danger')
      }
    } catch (e) {
      addToast(`Error de conexión al subir archivo`, 'danger')
    }
  }

  const handleAddClient = async () => {
    if (!newClient.ruc || !newClient.razon_social) {
      addToast('RUC y Razón Social son obligatorios', 'warning')
      return
    }
    const { data, error } = await supabase.from('clientes').insert([newClient]).select()
    if (error) {
      addToast(`Error al agregar: ${error.message}`, 'danger')
    } else if (data && data.length > 0) {
      addToast('Cliente agregado correctamente', 'success')
      setClientes([...clientes, data[0]])
      setSelectedCliente(data[0].id)
      setShowAddClientModal(false)
      setNewClient({ ruc: '', razon_social: '', usuario_sol: '', clave_sol: '', rubro: '', cuentas_contables: '' })
    }
  }

  const handleSaveClient = async () => {
    if (!editingClient) return
    const { error } = await supabase.from('clientes').update({
      usuario_sol: editingClient.usuario_sol,
      clave_sol: editingClient.clave_sol,
      client_id_api: editingClient.client_id_api,
      client_secret_api: editingClient.client_secret_api,
      rubro: editingClient.rubro,
      cuentas_contables: editingClient.cuentas_contables
    }).eq('id', editingClient.id)

    if (error) addToast(`Error al guardar: ${error.message}`, 'danger')
    else {
      addToast('Credenciales guardadas', 'success')
      setClientes(clientes.map(c => c.id === editingClient.id ? editingClient : c))
      setShowSettingsModal(false)
    }
  }

  const handleExportExcel = (urlOrAction) => {
    if (!selectedCliente || !selectedPeriodo) return
    const url = `${API_BASE_URL}/api/export/excel/${selectedCliente}/${selectedPeriodo}`
    const a = document.createElement('a')
    a.href = url
    a.download = true
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const handleExportPdfs = async (tipo_libro) => {
    const cliente = clientes.find(c => c.id === selectedCliente)
    if (!cliente) return
    
    addToast(`Generando PDF consolidado de ${tipo_libro}...`, 'info')
    try {
      const response = await fetch(`${API_BASE_URL}/api/export/pdf-merged`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ruc: cliente.ruc, periodo: selectedPeriodo, tipo_libro, allow_incomplete: true })
      })
      if (!response.ok) {
        const errorData = await response.json()
        addToast(`Error: ${errorData.detail || 'Error al generar PDF'}`, 'danger')
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
      addToast(`PDF consolidado de ${tipo_libro} descargado.`, 'success')
    } catch (e) {
      addToast(`Error de conexión al exportar.`, 'danger')
    }
  }

  const handleExportPreliminarExcel = async () => {
    const cliente = clientes.find(c => c.id === selectedCliente)
    if (!cliente || !selectedPeriodo) return
    
    addToast(`Generando Excel Preliminar con liquidación de impuestos...`, 'info')
    try {
      const response = await fetch(`${API_BASE_URL}/api/export/preliminar-excel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ruc: cliente.ruc, periodo: selectedPeriodo })
      })
      if (!response.ok) {
        addToast(`Error al generar Excel preliminar`, 'danger')
        return
      }
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `Preliminar_${cliente.ruc}_${selectedPeriodo}.xlsx`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      addToast(`Excel Preliminar descargado.`, 'success')
    } catch (e) {
      addToast(`Error de conexión al exportar.`, 'danger')
    }
  }

  const currentClient = clientes.find(c => c.id === selectedCliente)
  const isReadyToProcess = selectedCliente && selectedPeriodo

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar animate-slide-up">
        <div className="brand">
          <h1>Contax</h1>
          <p>Inteligencia Contable</p>
        </div>


        {/* Main tab navigation - hidden temporarily */}
        <div className="main-tabs-container" style={{display: 'none'}}>
          <button 
            className={`main-tab-btn ${activeMainTab === 'contabilidad' ? 'active' : ''}`}
            onClick={() => setActiveMainTab('contabilidad')}
          >
            <Calculator size={18} />
            <span>Contabilidad Automática</span>
          </button>
          <button 
            className={`main-tab-btn ${activeMainTab === 'facturacion' ? 'active' : ''}`}
            onClick={() => setActiveMainTab('facturacion')}
          >
            <FileText size={18} />
            <span>Facturación y Guías</span>
          </button>
        </div>


        <div className="sidebar-controls">
          <div className="control-group">
            <label>Cliente</label>
            <div style={{display: 'flex', gap: '0.5rem'}}>
              <input
                list="clientes-datalist"
                placeholder="Buscar RUC o Nombre..."
                value={clientSearchText}
                onChange={e => {
                  const val = e.target.value;
                  setClientSearchText(val);
                  const found = clientes.find(c => `${c.ruc} - ${c.razon_social}` === val);
                  if (found) setSelectedCliente(found.id);
                  else if (val === '') setSelectedCliente('');
                }}
                style={{flex: 1, width: '100%'}}
              />
              <button className="btn btn-primary" style={{padding: '0.5rem', width: 'auto'}} onClick={() => setShowAddClientModal(true)} title="Agregar Cliente">
                <UserPlus size={18} />
              </button>
            </div>
            <datalist id="clientes-datalist">
              {clientes.map(c => <option key={c.id} value={`${c.ruc} - ${c.razon_social}`} />)}
            </datalist>
          </div>

          <div className="control-group">
            <label>Periodo</label>
            <select value={selectedPeriodo} onChange={e => setSelectedPeriodo(e.target.value)}>
              <option value="">Seleccionar...</option>
              {STATIC_PERIODS.map(p => (
                <option key={p} value={p}>{formatPeriod(p)}</option>
              ))}
            </select>
          </div>

          {currentClient && (
            <div className="control-group" style={{marginTop: '1rem', padding: '1.2rem', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px'}}>
              <div style={{fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.3rem'}}>Giro / Rubro</div>
              <div style={{color: '#e2e8f0', fontSize: '0.9rem', marginBottom: '1rem', fontWeight: 500}}>{currentClient.rubro || 'General'}</div>
              
              <div style={{fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.3rem'}}>Clasificación IA (Cuentas)</div>
              <div style={{color: currentClient.cuentas_contables ? '#a78bfa' : '#94a3b8', fontSize: '0.85rem', lineHeight: '1.4'}}>
                {currentClient.cuentas_contables || 'Uso de Plan Contable General (PCGE completo)'}
              </div>

              <button className="btn btn-secondary" style={{marginTop: '1.5rem', width: '100%', fontSize: '0.85rem'}} onClick={() => setShowSettingsModal(true)}>
                <Settings size={15} /> Ajustar Configuración
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content animate-fade-in" style={{animationDelay: '0.1s'}}>
        {activeMainTab === 'contabilidad' ? (
          <>
        
        {/* Steps / Wizard */}
        <div className="steps-container">
          {STEPS.map((step) => {
            const Icon = step.icon;
            const isActive = activeStep === step.id;
            return (
              <div 
                key={step.id} 
                className={`glass-panel step-card ${isActive ? 'active' : ''}`}
                onClick={() => setActiveStep(step.id)}
              >
                <div className="step-header">
                  <div className="step-number">{step.id}</div>
                  <div className="step-title">{step.title}</div>
                </div>
                
                {/* Botones de acción contextuales por paso */}
                {isActive && (
                  <div className="step-actions animate-fade-in">
                    {step.id === 1 && (
                      <>
                        <button disabled={!isReadyToProcess || !!activeTaskId} onClick={() => handleBotAction('download-api')} className="btn btn-outline">
                          <UploadCloud size={16} /> 1. Propuesta SIRE API
                        </button>
                        <button disabled={!isReadyToProcess || !!activeTaskId} onClick={handleSyncSireFisicos} className="btn btn-primary">
                          <Database size={16} /> 2. Autenticar & Descargar Físicos
                        </button>
                        <button disabled={!isReadyToProcess || !!activeTaskId} onClick={handleResetPendientes} className="btn btn-warning" style={{background: 'linear-gradient(135deg, #f59e0b, #d97706)'}}>
                          <RefreshCcw size={16} /> Reintentar Fallidos
                        </button>
                        <button disabled={!isReadyToProcess || !!activeTaskId} onClick={() => handleExportPdfs('COMPRAS')} className="btn btn-secondary">
                          <Download size={16} /> Consolidar PDFs Compras
                        </button>
                        <button disabled={!isReadyToProcess || !!activeTaskId} onClick={() => handleExportPdfs('VENTAS')} className="btn btn-secondary">
                          <Download size={16} /> Consolidar PDFs Ventas
                        </button>
                        <button disabled={!isReadyToProcess || !!activeTaskId} onClick={handleExportPreliminarExcel} className="btn btn-primary" style={{background: 'linear-gradient(135deg, #10b981, #047857)'}}>
                          <Download size={16} /> {!!activeTaskId ? 'Sincronizando...' : 'Excel Preliminar'}
                        </button>
                      </>
                    )}
                    {step.id === 2 && (
                      <>
                        <button disabled={!isReadyToProcess || !!activeTaskId} onClick={() => handleBotAction('enrich-xml')} className="btn btn-primary" style={{background: 'linear-gradient(135deg, #ec4899, #be185d)'}}>
                          <Search size={16} /> Extraer Glosas de XML
                        </button>
                        <button disabled={!isReadyToProcess || !!activeTaskId} onClick={() => handleBotAction('classify-ai')} className="btn btn-primary">
                          <BarChart3 size={16} /> Clasificar con Inteligencia Artificial
                        </button>
                      </>
                    )}
                    {step.id === 3 && (
                      <>
                        <button disabled={!isReadyToProcess || !!activeTaskId} onClick={handleExportExcel} className="btn btn-primary" style={{background: 'linear-gradient(135deg, #10b981, #047857)'}}>
                          <Download size={16} /> Exportar Excel Final
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Terminal Log */}
        {(activeTaskId || terminalLogs) && (
          <div className="terminal-window animate-fade-in" style={{ height: isTerminalMinimized ? 'auto' : undefined }}>
            <div 
              className="terminal-header" 
              style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }} 
              onClick={() => setIsTerminalMinimized(!isTerminalMinimized)}
            >
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <Terminal size={14} style={{ marginRight: '8px' }} />
                <span>Proceso en ejecución: {activeTaskId || 'Finalizado'}</span>
                {activeTaskId && <Activity size={14} className="animate-pulse" style={{ color: '#10b981', marginLeft: '8px' }} />}
              </div>
              <button 
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                title={isTerminalMinimized ? "Expandir terminal" : "Minimizar terminal"}
              >
                {isTerminalMinimized ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>
            </div>
            {!isTerminalMinimized && (
              <pre className="terminal-content" ref={terminalRef}>
                {terminalLogs}
              </pre>
            )}
          </div>
        )}

        {/* Data Table */}
        <div className="glass-panel data-panel animate-slide-up" style={{animationDelay: '0.2s'}}>
          <div className="table-header-actions">
            <div className="table-title">
              {(() => {
                const StepIcon = STEPS.find(s => s.id === activeStep)?.icon;
                return StepIcon ? <StepIcon size={20} color="#a78bfa" /> : null;
              })()}
              Vista de Datos
            </div>
            <div style={{fontSize: '0.85rem', color: 'var(--text-muted)'}}>
              Mostrando {Math.min(itemsToShow, data.length)} de {data.length} comprobantes
            </div>
          </div>
          
          <div className="table-container">
            {loading ? (
              <div style={{textAlign: 'center', padding: '3rem', color: 'var(--text-muted)'}}>
                <RefreshCcw className="animate-spin" size={32} style={{margin: '0 auto 1rem'}} />
                Cargando datos...
              </div>
            ) : data.length > 0 ? (
              <table>
                <thead>
                  <tr>
                    <th>Tipo</th>
                    <th>Serie-Número</th>
                    <th>Fecha</th>
                    <th>RUC Tercero</th>
                    {activeStep === 1 && (
                      <>
                        <th>Estado XML</th>
                        <th>Estado PDF</th>
                      </>
                    )}
                    {activeStep === 2 && (
                      <>
                        <th>Glosa / Descripción</th>
                        <th>Categoría IA</th>
                        <th>Cuenta Contable</th>
                      </>
                    )}
                    <th>Monto Total</th>
                  </tr>
                </thead>
                <tbody>
                  {data.slice(0, itemsToShow).map((row, i) => (
                    <tr key={i}>
                      <td>
                        <span className={`badge ${row.tipo === 'VENTA' || row.tipo_libro === 'VENTAS' ? 'badge-success' : 'badge-warning'}`}>
                          {row.tipo || row.tipo_libro}
                        </span>
                      </td>
                      <td>{row.serie_cdp || row.serie}-{row.nro_cp || row.numero}</td>
                      <td>{row.fecha_emision || '-'}</td>
                      <td>{row.nro_doc_identidad || row.ruc_tercero}</td>
                      
                      {activeStep === 1 && (
                        <>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span className={`badge ${row.estado_xml === 'DESCARGADO' ? 'badge-success' : 'badge-danger'}`}>{row.estado_xml || '-'}</span>
                              <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', color: '#a78bfa', margin: 0 }} title="Subir XML manual">
                                <Upload size={14} />
                                <input type="file" accept=".xml,.zip" style={{ display: 'none' }} onChange={(e) => handleManualUpload(row.id, e.target.files[0], 'xml')} />
                              </label>
                            </div>
                          </td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span className={`badge ${row.estado_pdf === 'DESCARGADO' ? 'badge-success' : 'badge-danger'}`}>{row.estado_pdf || '-'}</span>
                              <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', color: '#a78bfa', margin: 0 }} title="Subir PDF manual">
                                <Upload size={14} />
                                <input type="file" accept=".pdf" style={{ display: 'none' }} onChange={(e) => handleManualUpload(row.id, e.target.files[0], 'pdf')} />
                              </label>
                            </div>
                          </td>
                        </>
                      )}

                      {activeStep === 2 && (
                        <>
                          <td style={{maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                            {row.descripcion_comprobante || 'Sin descripción'}
                          </td>
                          <td><span className={`badge ${row.categoria ? 'badge-purple' : 'badge-warning'}`}>{row.categoria || 'Pendiente'}</span></td>
                          <td><strong style={{color: '#c4b5fd'}}>{row.cuenta_contable || '-'}</strong></td>
                        </>
                      )}

                      <td>S/ {Number(row.total_cp || row.monto_total || row.mto_imp_venta || 0).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{textAlign: 'center', padding: '3rem', color: 'var(--text-muted)'}}>
                Selecciona un cliente y un periodo para visualizar la información.
              </div>
            )}
          </div>
          
          {data.length > itemsToShow && (
            <div style={{padding: '1rem', textAlign: 'center'}}>
              <button className="btn btn-secondary" style={{width: 'auto', margin: '0 auto'}} onClick={() => setItemsToShow(p => p + 50)}>
                Cargar más resultados
              </button>
            </div>
          )}
        </div>

                </>
        ) : (
          <FacturacionView 
            clientes={clientes}
            selectedCliente={selectedCliente}
            onSelectCliente={setSelectedCliente}
            addToast={addToast}
            apiBaseUrl={API_BASE_URL}
          />
        )}
      </main>

      {/* Settings Modal */}
      {showSettingsModal && editingClient && (
        <div className="modal-overlay" onClick={() => setShowSettingsModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div style={{display:'flex', justifyContent:'space-between', marginBottom:'1.5rem'}}>
              <h3 style={{color:'#f8fafc'}}>Configuración de Cliente</h3>
              <button onClick={() => setShowSettingsModal(false)} style={{background:'none', border:'none', color:'#94a3b8', cursor:'pointer'}}><X size={20}/></button>
            </div>
            
            <div className="control-group" style={{marginBottom: '1rem'}}>
              <label>RUC</label>
              <input type="text" value={editingClient.ruc} disabled />
            </div>
            <div className="control-group" style={{marginBottom: '1rem'}}>
              <label>Razón Social</label>
              <input type="text" value={editingClient.razon_social} disabled />
            </div>
            <div style={{display:'flex', gap:'1rem', marginBottom: '1rem'}}>
              <div className="control-group" style={{flex: 1}}>
                <label>Usuario SOL</label>
                <input type="text" value={editingClient.usuario_sol || ''} onChange={e => setEditingClient({...editingClient, usuario_sol: e.target.value})} />
              </div>
              <div className="control-group" style={{flex: 1}}>
                <label>Clave SOL</label>
                <input type="text" value={editingClient.clave_sol || ''} onChange={e => setEditingClient({...editingClient, clave_sol: e.target.value})} />
              </div>
            </div>
            <div style={{display:'flex', gap:'1rem', marginBottom: '1rem'}}>
              <div className="control-group" style={{flex: 1}}>
                <label>Client ID (API)</label>
                <input type="text" value={editingClient.client_id_api || ''} onChange={e => setEditingClient({...editingClient, client_id_api: e.target.value})} />
              </div>
              <div className="control-group" style={{flex: 1}}>
                <label>Client Secret (API)</label>
                <input type="text" value={editingClient.client_secret_api || ''} onChange={e => setEditingClient({...editingClient, client_secret_api: e.target.value})} />
              </div>
            </div>
            
            <div className="control-group" style={{marginBottom: '1rem'}}>
              <label>Cuentas Contables (Personalizadas)</label>
              <textarea 
                placeholder="Ej: 6011 (Mercaderías), 6311 (Transporte)"
                value={editingClient.cuentas_contables || ''} 
                onChange={e => setEditingClient({...editingClient, cuentas_contables: e.target.value})} 
                rows="3"
                style={{
                  fontFamily: 'Inter', background: 'rgba(0, 0, 0, 0.3)', 
                  border: '1px solid rgba(255, 255, 255, 0.1)', color: 'var(--text-main)', 
                  padding: '0.6rem 1rem', borderRadius: '8px', width: '100%', resize: 'vertical'
                }}
              />
              <span style={{fontSize: '0.75rem', color: 'var(--text-muted)'}}>
                La Inteligencia Artificial usará SOLAMENTE estas cuentas para este cliente. Si está vacío, usará el Plan Contable general.
              </span>
            </div>
            
            <div style={{display:'flex', justifyContent:'flex-end', gap:'1rem', marginTop:'2rem'}}>
              <button className="btn btn-secondary" style={{width:'auto'}} onClick={() => setShowSettingsModal(false)}>Cancelar</button>
              <button className="btn btn-primary" style={{width:'auto'}} onClick={handleSaveClient}>Guardar Cambios</button>
            </div>
          </div>
        </div>
      )}

      {/* Add Client Modal */}
      {showAddClientModal && (
        <div className="modal-overlay" onClick={() => setShowAddClientModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div style={{display:'flex', justifyContent:'space-between', marginBottom:'1.5rem'}}>
              <h3 style={{color:'#f8fafc'}}>Agregar Nuevo Cliente</h3>
              <button onClick={() => setShowAddClientModal(false)} style={{background:'none', border:'none', color:'#94a3b8', cursor:'pointer'}}><X size={20}/></button>
            </div>
            <div className="control-group" style={{marginBottom: '1rem'}}>
              <label>RUC *</label>
              <input type="text" value={newClient.ruc} onChange={e => setNewClient({...newClient, ruc: e.target.value})} placeholder="Ej: 20123456789" />
            </div>
            <div className="control-group" style={{marginBottom: '1rem'}}>
              <label>Razón Social *</label>
              <input type="text" value={newClient.razon_social} onChange={e => setNewClient({...newClient, razon_social: e.target.value})} placeholder="Ej: MI EMPRESA S.A.C." />
            </div>
            <div className="control-group" style={{marginBottom: '1rem'}}>
              <label>Rubro / Giro de Negocio</label>
              <input type="text" value={newClient.rubro || ''} onChange={e => setNewClient({...newClient, rubro: e.target.value})} placeholder="Ej: Venta de abarrotes, Transporte..." />
            </div>
            <div className="control-group" style={{marginBottom: '1rem'}}>
              <label>Cuentas Contables (Personalizadas)</label>
              <textarea 
                placeholder="Ej: 6011 (Mercaderías), 6311 (Transporte)"
                value={newClient.cuentas_contables || ''} 
                onChange={e => setNewClient({...newClient, cuentas_contables: e.target.value})} 
                rows="2"
                style={{
                  fontFamily: 'Inter', background: 'rgba(0, 0, 0, 0.3)', 
                  border: '1px solid rgba(255, 255, 255, 0.1)', color: 'var(--text-main)', 
                  padding: '0.6rem 1rem', borderRadius: '8px', width: '100%', resize: 'vertical'
                }}
              />
            </div>
            <div style={{display:'flex', justifyContent:'flex-end', gap:'1rem', marginTop:'2rem'}}>
              <button className="btn btn-secondary" style={{width:'auto'}} onClick={() => setShowAddClientModal(false)}>Cancelar</button>
              <button className="btn btn-primary" style={{width:'auto'}} onClick={handleAddClient}>Guardar Cliente</button>
            </div>
          </div>
        </div>
      )}

      {/* Toasts */}
      <div className="toast-container">
        {notifications.map(n => (
          <div key={n.id} className="toast" style={{
            borderLeft: `4px solid ${n.type === 'success' ? 'var(--success)' : n.type === 'danger' ? 'var(--danger)' : n.type === 'warning' ? 'var(--warning)' : 'var(--accent-primary)'}`
          }}>
            {n.msg}
          </div>
        ))}
      </div>
    </div>
  )
}

export default App
