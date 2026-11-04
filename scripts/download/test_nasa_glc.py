import requests, json

# Test NASA GLC via Socrata API
print('=== Testing NASA GLC Socrata API ===')
base = 'https://data.nasa.gov/resource/dd9e-wu2v.json'
params = {'country_name': 'India', '$limit': 5000, '$offset': 0}
try:
    r = requests.get(base, params=params, timeout=30, headers={'X-App-Token': 'DEMO_KEY'})
    print('Status:', r.status_code)
    if r.status_code == 200:
        data = r.json()
        print('India records:', len(data))
        if data:
            print('Keys:', list(data[0].keys()))
            ne_states = ['mizoram','manipur','meghalaya','nagaland','tripura','assam','arunachal','sikkim']
            ne = [d for d in data if any(s in str(d).lower() for s in ne_states)]
            print('NE India total:', len(ne))
            bbox_match = []
            for d in data:
                try:
                    lat = float(d.get('latitude') or 0)
                    lon = float(d.get('longitude') or 0)
                    if 21.9 <= lat <= 24.6 and 92.1 <= lon <= 93.5:
                        bbox_match.append(d)
                except:
                    pass
            print('Bbox match (Mizoram):', len(bbox_match))
            for b in bbox_match:
                print(' ', b.get('event_date'), b.get('location_description'), b.get('latitude'), b.get('longitude'))
    else:
        print(r.text[:300])
except Exception as ex:
    print('Error:', ex)
