import sys
from pathlib import Path
def _repo_root():
    return Path(__file__).resolve().parent
if str(_repo_root()) not in sys.path:
    sys.path.insert(0, str(_repo_root()))

from app.brain.db.supabase_client import get_supabase

clientes = [
    {'razon_social': 'MEDRANO GARCIA ADOLFO CESAR', 'ruc': '10407861642', 'usuario_sol': 'FMAVCIDV', 'clave_sol': '4bjZVbmQZ'},
    {'razon_social': 'CLINICA DENTAL SANTA INES REPRESENTACIONES', 'ruc': '20482192841', 'usuario_sol': 'SMISTIVA', 'clave_sol': 'condsoneu'},
    {'razon_social': 'DJULIETTE EIRL', 'ruc': '20611775661', 'usuario_sol': '47006261', 'clave_sol': '220619Jj'},
    {'razon_social': 'FERNANDEZ GONZALES ROSELLA ELISA', 'ruc': '10405610871', 'usuario_sol': 'GNBERMIC', 'clave_sol': 'Rosella2023'},
    {'razon_social': 'JS ARQUITECTURA Y CONSTRUCCION S.A.C.', 'ruc': '20600438621', 'usuario_sol': 'LUMEMINE', 'clave_sol': 'Jonars2024'},
    {'razon_social': 'MINERCO COMPANY EIRL', 'ruc': '20613022571', 'usuario_sol': '45111689', 'clave_sol': 'Varela3030'},
    {'razon_social': 'CONSTRUCCIONES NECAN E.I.R.L.', 'ruc': '20603527462', 'usuario_sol': 'NECANEIR', 'clave_sol': 'Necan2025'},
    {'razon_social': 'PROSPERY VIAJES Y TURISMO EIRL', 'ruc': '20482345183', 'usuario_sol': 'IATEMONA', 'clave_sol': 'doneyboax'},
    {'razon_social': 'TICLAVILCA PAREDES EFRAIN ANTONIO', 'ruc': '10198550324', 'usuario_sol': 'TPEFRAIN', 'clave_sol': '090613Pte'},
    {'razon_social': 'ECOSERVIS 3M E.I.R.L.', 'ruc': '20614169754', 'usuario_sol': '18222009', 'clave_sol': 'Moises2025'},
    {'razon_social': 'CONDOR BRICEÑO SANTOS JAIME', 'ruc': '10418208665', 'usuario_sol': 'FLOGYMAR', 'clave_sol': 'ranettonc'},
    {'razon_social': 'ARANDA VEGA JOSE JEAN PIERRE', 'ruc': '10735898707', 'usuario_sol': '73589870', 'clave_sol': 'Aranda2025'},
    {'razon_social': 'MAELOS CAR WASH SAC', 'ruc': '20613387677', 'usuario_sol': '76395623', 'clave_sol': 'Maelo2100'},
    {'razon_social': 'GRUPO PADILLA INTEGRAL S.A.C', 'ruc': '20614492377', 'usuario_sol': '42090610', 'clave_sol': 'Pena2025'}
]

supabase = get_supabase()
for c in clientes:
    try:
        supabase.table('clientes').upsert(c, on_conflict='ruc').execute()
        print(f"Inserted {c['ruc']} - {c['razon_social']}")
    except Exception as e:
        print(f"Failed for {c['ruc']}: {e}")
