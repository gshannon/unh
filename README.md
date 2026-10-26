# casco

Casco Bay data project

Run tests: python -m unittest discover -s test -t .

Get sites:

app/tools/sites.py [--max N] # default=5

Get datastreams for CundyHarbor:

app/tools/datastreams.py --site-id 68ae13a5f9101a3a0812f688

Get observations for 2 streams:

app/tools/observations.py --datastream-id1 2282797 --datastream-id2 2282794 --start-time 2026-10-20T08:00 --end-time 2026-10-20T09:00
