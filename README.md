# UNH Data Project

This project has 3 Python programs which call APIs, generate csv files, and uploads them to a UNH server.

1. get-wells.py: pulls Wells SWMP data from CDMO
1. get-harpswell.py --type E [opt args]: pulls Harpswell EXO data from Xylem.
1. get-harpswell.py --type M [opt args]: pulls Harpswell MET data from Xylem.

## Arguments

- You may specify a date range by providing the _--start_ and _--end_ arguments, or run in auto mode by omitting them.
- If in auto mode, it will read/write a small file which contains the timestamp of the latest data item sent.
- All modes will create or overwrite a data file named like _PREFIX-YYYYMMDD-HHMM.csv_ where PREFIX indicates the data type and the datetime is that of the first data element contained in the file.
- You may specify the _--dryrun_ parameter to skip writing the timestamp file and uploading to the ftp site.
- You may specify the _--verbose_ parameter to see debug level output
- You may specify the _--noftp_ parameter to skip the ftp upload.

## Security

These variables must be defined in an .env file:

_Xylem API_

- API_CLIENT_ID
- API_CLIENT_SECRET

_CDMO_

- CDMO_USER
- CDMO_PASSWORD

_UNH_

- TARGET_IP
- TARGET_USER
- TARGET_PASSWORD

## Tests

Run tests: python -m unittest discover -s test -t .
