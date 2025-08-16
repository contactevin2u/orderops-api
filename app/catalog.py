from typing import List, Dict, Any

CATALOG: List[Dict[str, Any]] = [
    # Hospital beds
    {"sku":"BED-2F-MAN","name":"Hospital Bed 2 Function (Manual)","sale_price":3200.0,"rent_monthly":360.0,"buyback_rate":0.40,"aliases":["katil 2 fungsi","hospital bed 2 function","bed 2 function"]},
    {"sku":"BED-3F-MAN","name":"Hospital Bed 3 Function (Manual)","sale_price":3800.0,"rent_monthly":420.0,"buyback_rate":0.42,"aliases":["katil 3 fungsi manual","hospital bed 3 function manual","bed 3 function manual"]},
    {"sku":"BED-5F-ELE","name":"Hospital Bed 5 Function (Electric)","sale_price":6200.0,"rent_monthly":580.0,"buyback_rate":0.45,"aliases":["katil 5 fungsi","hospital bed 5 function","bed 5 function electric"]},
    {"sku":"BED-3F-AUTO","name":"Hospital Bed 3 Function (Electric Auto)","sale_price":5200.0,"rent_monthly":520.0,"buyback_rate":0.44,"aliases":["katil 3 fungsi auto","hospital bed 3 function auto","bed 3 function electric"]},

    # Wheelchairs
    {"sku":"WHL-STD-STEEL","name":"Auto Wheelchair (Steel)","sale_price":650.0,"rent_monthly":120.0,"buyback_rate":0.35,"aliases":["wheelchair steel","kerusi roda besi","auto wheelchair steel"]},
    {"sku":"WHL-STD-ALU","name":"Auto Wheelchair (Aluminium)","sale_price":950.0,"rent_monthly":150.0,"buyback_rate":0.35,"aliases":["wheelchair aluminium","auto wheelchair aluminium","kerusi roda aluminium"]},
    {"sku":"WHL-HD-STEEL","name":"Heavy Duty Auto Wheelchair","sale_price":1400.0,"rent_monthly":220.0,"buyback_rate":0.35,"aliases":["heavy duty wheelchair","kerusi roda heavy duty","auto wheelchair heavy duty"]},

    # Oxygen
    {"sku":"O2-CONC-5L","name":"Oxygen Concentrator 5L","sale_price":2800.0,"rent_monthly":420.0,"buyback_rate":0.40,"aliases":["oxygen concentrator 5l","konsentrator oksigen 5l","mesin oksigen 5l"]},
    {"sku":"O2-CONC-10L","name":"Oxygen Concentrator 10L","sale_price":4200.0,"rent_monthly":560.0,"buyback_rate":0.40,"aliases":["oxygen concentrator 10l","konsentrator oksigen 10l","mesin oksigen 10l"]},
    {"sku":"O2-TANK","name":"Oxygen Tank","sale_price":600.0,"rent_monthly":110.0,"buyback_rate":0.20,"aliases":["tong oksigen","oxygen cylinder","gas oksigen"]},

    # Mattress example
    {"sku":"MAT-CANVAS","name":"Tilam Canvas","sale_price":199.0,"rent_monthly":None,"buyback_rate":0.10,"aliases":["tilam canvas","canvas mattress"]},
]
