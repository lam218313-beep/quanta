# Comandos de Ejecución por Cliente

A continuación tienes los comandos listos para copiar y pegar en tu terminal para procesar cada una de las empresas registradas en tu base de datos.

**Instrucciones de uso (Ciclo Abril 2026):**
1. **(Opcional pero Recomendado)** Copia y pega el comando de **Descargar Propuesta SIRE API**. Este paso se conecta a SUNAT para traer el listado oficial de facturas de Abril 2026 (`202604`) y lo carga a la base de datos. Si ya lo hiciste masivamente para todos, puedes saltar este paso.
2. Copia y pega el comando de **Generar Sesión (Autenticación)**. Se abrirá Chrome, se llenarán los datos y si hay captcha, resuélvelo y dale Entrar. El navegador se cerrará solo.
3. Copia y pega el comando de **Descargar Facturas Físicas**. El bot se encargará de descargar en segundo plano todos los XML y PDFs de ese periodo y empresa.

---

### 1. ARANDA VEGA JOSE JEAN PIERRE (RUC: 10735898707)
*Paso 1: Descargar Propuesta SIRE API (Abril 2026):*
```bash
python app/brain/sire_download_cli.py --period 202604 --client 10735898707
```
*Paso 2: Generar Sesión:*
```bash
python app/brain/automation_scraper.py --ruc 10735898707
```
*Paso 3: Descargar Facturas Físicas:*
```bash
python app/brain/db/sire_bot_orchestrator.py --limit 200 --ruc 10735898707
```

---

### 2. Arquitectura Babilonia (RUC: 20600373065)
*Paso 1: Descargar Propuesta SIRE API (Abril 2026):*
```bash
python app/brain/sire_download_cli.py --period 202604 --client 20600373065
```
*Paso 2: Generar Sesión:*
```bash
python app/brain/automation_scraper.py --ruc 20600373065
```
*Paso 3: Descargar Facturas Físicas:*
```bash
python app/brain/db/sire_bot_orchestrator.py --limit 200 --ruc 20600373065
```

---

### 3. CLINICA DENTAL SANTA INES REPRESENTACIONES (RUC: 20482192841)
*Paso 1: Descargar Propuesta SIRE API (Abril 2026):*
```bash
python app/brain/sire_download_cli.py --period 202604 --client 20482192841
```
*Paso 2: Generar Sesión:*
```bash
python app/brain/automation_scraper.py --ruc 20482192841
```
*Paso 3: Descargar Facturas Físicas:*
```bash
python app/brain/db/sire_bot_orchestrator.py --limit 200 --ruc 20482192841
```

---

### 4. CONDOR BRICEÑO SANTOS JAIME (RUC: 10418208665)
*Paso 1: Descargar Propuesta SIRE API (Abril 2026):*
```bash
python app/brain/sire_download_cli.py --period 202604 --client 10418208665
```
*Paso 2: Generar Sesión:*
```bash
python app/brain/automation_scraper.py --ruc 10418208665
```
*Paso 3: Descargar Facturas Físicas:*
```bash
python app/brain/db/sire_bot_orchestrator.py --limit 200 --ruc 10418208665
```

---

### 5. CONSTRUCCIONES NECAN E.I.R.L. (RUC: 20603527462)
*Paso 1: Descargar Propuesta SIRE API (Abril 2026):*
```bash
python app/brain/sire_download_cli.py --period 202604 --client 20603527462
```
*Paso 2: Generar Sesión:*
```bash
python app/brain/automation_scraper.py --ruc 20603527462
```
*Paso 3: Descargar Facturas Físicas:*
```bash
python app/brain/db/sire_bot_orchestrator.py --limit 200 --ruc 20603527462
```

---

### 6. DJULIETTE EIRL (RUC: 20611775661)
*Paso 1: Descargar Propuesta SIRE API (Abril 2026):*
```bash
python app/brain/sire_download_cli.py --period 202604 --client 20611775661
```
*Paso 2: Generar Sesión:*
```bash
python app/brain/automation_scraper.py --ruc 20611775661
```
*Paso 3: Descargar Facturas Físicas:*
```bash
python app/brain/db/sire_bot_orchestrator.py --limit 200 --ruc 20611775661
```

---

### 7. ECOSERVIS 3M E.I.R.L. (RUC: 20614169754)
*Paso 1: Descargar Propuesta SIRE API (Abril 2026):*
```bash
python app/brain/sire_download_cli.py --period 202604 --client 20614169754
```
*Paso 2: Generar Sesión:*
```bash
python app/brain/automation_scraper.py --ruc 20614169754
```
*Paso 3: Descargar Facturas Físicas:*
```bash
python app/brain/db/sire_bot_orchestrator.py --limit 200 --ruc 20614169754
```

---

### 8. FERNANDEZ GONZALES ROSELLA ELISA (RUC: 10405610871)
*Paso 1: Descargar Propuesta SIRE API (Abril 2026):*
```bash
python app/brain/sire_download_cli.py --period 202604 --client 10405610871
```
*Paso 2: Generar Sesión:*
```bash
python app/brain/automation_scraper.py --ruc 10405610871
```
*Paso 3: Descargar Facturas Físicas:*
```bash
python app/brain/db/sire_bot_orchestrator.py --limit 200 --ruc 10405610871
```

---

### 9. GRUPO PADILLA INTEGRAL S.A.C (RUC: 20614492377)
*Paso 1: Descargar Propuesta SIRE API (Abril 2026):*
```bash
python app/brain/sire_download_cli.py --period 202604 --client 20614492377
```
*Paso 2: Generar Sesión:*
```bash
python app/brain/automation_scraper.py --ruc 20614492377
```
*Paso 3: Descargar Facturas Físicas:*
```bash
python app/brain/db/sire_bot_orchestrator.py --limit 200 --ruc 20614492377
```

---

### 10. JS ARQUITECTURA Y CONSTRUCCION S.A.C. (RUC: 20600438621)
*Paso 1: Descargar Propuesta SIRE API (Abril 2026):*
```bash
python app/brain/sire_download_cli.py --period 202604 --client 20600438621
```
*Paso 2: Generar Sesión:*
```bash
python app/brain/automation_scraper.py --ruc 20600438621
```
*Paso 3: Descargar Facturas Físicas:*
```bash
python app/brain/db/sire_bot_orchestrator.py --limit 200 --ruc 20600438621
```

---

### 11. MAELOS CAR WASH SAC (RUC: 20613387677)
*Paso 1: Descargar Propuesta SIRE API (Abril 2026):*
```bash
python app/brain/sire_download_cli.py --period 202604 --client 20613387677
```
*Paso 2: Generar Sesión:*
```bash
python app/brain/automation_scraper.py --ruc 20613387677
```
*Paso 3: Descargar Facturas Físicas:*
```bash
python app/brain/db/sire_bot_orchestrator.py --limit 200 --ruc 20613387677
```

---

### 12. MEDRANO GARCIA ADOLFO CESAR (RUC: 10407861642)
*Paso 1: Descargar Propuesta SIRE API (Abril 2026):*
```bash
python app/brain/sire_download_cli.py --period 202604 --client 10407861642
```
*Paso 2: Generar Sesión:*
```bash
python app/brain/automation_scraper.py --ruc 10407861642
```
*Paso 3: Descargar Facturas Físicas:*
```bash
python app/brain/db/sire_bot_orchestrator.py --limit 200 --ruc 10407861642
```

---

### 13. MINERCO COMPANY EIRL (RUC: 20613022571)
*Paso 1: Descargar Propuesta SIRE API (Abril 2026):*
```bash
python app/brain/sire_download_cli.py --period 202604 --client 20613022571
```
*Paso 2: Generar Sesión:*
```bash
python app/brain/automation_scraper.py --ruc 20613022571
```
*Paso 3: Descargar Facturas Físicas:*
```bash
python app/brain/db/sire_bot_orchestrator.py --limit 200 --ruc 20613022571
```

---

### 14. PROSPERY VIAJES Y TURISMO EIRL (RUC: 20482345183)
*Paso 1: Descargar Propuesta SIRE API (Abril 2026):*
```bash
python app/brain/sire_download_cli.py --period 202604 --client 20482345183
```
*Paso 2: Generar Sesión:*
```bash
python app/brain/automation_scraper.py --ruc 20482345183
```
*Paso 3: Descargar Facturas Físicas:*
```bash
python app/brain/db/sire_bot_orchestrator.py --limit 200 --ruc 20482345183
```

---

### 15. TICLAVILCA PAREDES EFRAIN ANTONIO (RUC: 10198550324)
*Paso 1: Descargar Propuesta SIRE API (Abril 2026):*
```bash
python app/brain/sire_download_cli.py --period 202604 --client 10198550324
```
*Paso 2: Generar Sesión:*
```bash
python app/brain/automation_scraper.py --ruc 10198550324
```
*Paso 3: Descargar Facturas Físicas:*
```bash
python app/brain/db/sire_bot_orchestrator.py --limit 200 --ruc 10198550324
```
