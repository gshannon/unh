# UNH Data Project

This project has 3 Python programs which call APIs, generate csv files, and uploads them to a UNH server.

1. get-wells.py: pulls Wells SWMP data from CDMO
1. get-harpswell.py --type E [opt args]: pulls Harpswell EXO data from Xylem.
1. get-harpswell.py --type M [opt args]: pulls Harpswell MET data from Xylem.

## General Flow

- All datetimes are in UTC
- Parses the command line. if _--start_ and _--end_ are given, uses this date range. Otherwise, it's in auto mode.
- If in auto mode, reads a small marker file which contains the timestamp of the latest data item sent. This plus one minute will be the start time. If the marker file does not exist, the start time defaults to 2 hours ago. The end time is the current time.
- Pulls the data from the data provider.
- If no data is available, exits.
- Converts any missing data to _NaN_ and sorts the data by observation time
- Writes a csv file named _PREFIX-YYYYMMDD-HHMM.csv_ where PREFIX indicates the data type and the datetime is that of the first data element contained in the file.
- If in auto mode, writes/overwrites the datetime of the last data row to the marker file.
- Uploads the csv file to the UNH ftp site.

## Special Case for Wells water level

Normally, any missing fields will be returned as _NaN_. But because the most recent data point that CDMO returns usually has a missing corrected level (_cLevel_) which is then made available later, once it has processed the weather data. Therefore, any such trailing records from CDMO (i.e. at the tail end of the current data) will be ignored -- not used for the marker file and not included in the output.

## Arguments

- _--start_ and _--end_: use this date range instead of the default auto mode
- _--type_ <x> : for Harpswell jobs; E=EXO, M=MET
- _--dryrun_ : do not write the marker file or do the ftp upload
- _--noftp_ do not do the ftp upload
- _--verbose_: see debug level output

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

## Example CSV content

_Wells_

    timestamp,Temp,DO_MgL,SpCond,cLevel,Sal,pH,DO_pct,Turb
    2026-11-03T13:15:00+00:00,11.6,8.7,49.99,0.40,32.6,7.9,98.7,2
    2026-11-03T13:30:00+00:00,11.6,8.7,50.00,0.26,32.6,7.9,98.5,2
    2026-11-03T13:45:00+00:00,11.7,8.7,49.95,0.12,32.6,7.9,98.6,2
    2026-11-03T14:00:00+00:00,11.7,8.7,50.00,-0.05,32.6,7.9,98.8,2

_Harpswell EXO_

    timestamp,Chlorophyll_ug/L,Phycoerythrin_ug/L,DO_Sat,SpCond_uS/cm,DO_mg/L,pH,ExoSamplesCounter,Date,Time,Salinity_PSU,Sonde_Battery_Power_V,Depth_m,Temp_DegC,Turbidity_NTU,pH_mV
    2026-11-03T13:16:04+00:00,2.6,5.03,85.28,49347.0,7.62,7.96,13343.0,31126.0,71500.0,32.15,5.85,3.975,11.31,0.63,-68.55
    2026-11-03T13:31:04+00:00,2.31,4.65,85.08,49343.2,7.6,7.96,13344.0,31126.0,73000.0,32.14,5.85,3.864,11.306,0.31,-68.55
    2026-11-03T13:46:04+00:00,3.31,4.85,87.37,49349.8,7.81,7.98,13345.0,31126.0,74500.0,32.15,5.85,3.726,11.311,0.24,-69.83
    2026-11-03T14:01:04+00:00,2.33,4.53,86.65,49342.5,7.74,7.97,13346.0,31126.0,80000.0,32.14,5.85,3.587,11.313,0.28,-69.17

_Harpswell MET_

    timestamp,Strikes,CompassHd_deg,NorthWSpd_ms,SlrFD_W,AirT_C,MaxWSpd_ms,BP_kPa,MaxWS_ms,Dist_km,TiltNS_deg,EastWSpd_ms,RH,METSamplesCounter,Rain_mm,RHT_C,TiltWE_deg,WS_ms,WindDir,VP_kPa
    2026-11-03T13:15:04+00:00,0.0,0.0,0.2,18.0,11.5,1.42,102.28,1.42,0.0,0.8,-0.49,0.9,13343.0,0.0,11.5,-1.6,0.53,291.9,1.22
    2026-11-03T13:30:04+00:00,0.0,0.0,0.02,28.4,11.6,1.2,102.33,1.2,0.0,0.9,-0.5,0.9,13344.0,0.0,11.6,-1.6,0.5,272.3,1.22
    2026-11-03T13:45:04+00:00,0.0,0.0,0.44,45.7,11.5,1.14,102.35,1.14,0.0,0.8,0.32,0.91,13345.0,0.0,11.8,-1.6,0.55,35.5,1.23
    2026-11-03T14:00:04+00:00,0.0,0.0,1.49,63.6,11.4,2.86,102.33,2.86,0.0,0.9,0.68,0.92,13346.0,0.0,11.9,-1.6,1.64,24.6,1.24
