import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv('d:\\Contax - copia - copia\\.env')
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')
supabase = create_client(url, key)

res = supabase.table('sire_comprobantes_fisicos').select('*').execute()
records = res.data

from collections import Counter
counts = Counter()
for r in records:
    counts[r['periodo']] += 1
    if r.get('ruta_pdf') and os.path.exists(r['ruta_pdf']):
        counts[f"pdf_{r['periodo']}"] += 1
    if r.get('ruta_xml'):
        counts[f"xml_{r['periodo']}"] += 1

print('Total records:', len(records))
for k, v in counts.items():
    print(k, v)
