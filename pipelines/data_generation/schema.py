"""Column definitions and constants for the fraud detection dataset."""

# TabFormer-inspired schema
COLUMNS = [
    "user_id",
    "card_id",
    "merchant_name",
    "merchant_city",
    "merchant_state",
    "merchant_country",
    "mcc",
    "amount",
    "hour",
    "minute",
    "day",
    "month",
    "year",
    "zip_code",
    "use_chip",
    "errors",
    "is_fraud",
]

# Generation parameters
N_USERS = 2000
N_MERCHANTS = 500
N_TRANSACTIONS = 200_000
FRAUD_RATE = 0.03

# MCC codes (Merchant Category Codes) with descriptions
MCC_CODES = {
    5411: "Grocery Stores",
    5541: "Gas Stations",
    5812: "Restaurants",
    5912: "Drug Stores",
    5311: "Department Stores",
    5211: "Hardware Stores",
    5945: "Hobby/Toy Stores",
    5651: "Family Clothing",
    5941: "Sporting Goods",
    5732: "Electronics",
    5999: "Misc Retail",
    4814: "Telecom Services",
    7011: "Hotels/Motels",
    7538: "Auto Service",
    5691: "Clothing Stores",
    5814: "Fast Food",
    5921: "Package Stores (Liquor)",
    5944: "Jewelry Stores",
    5200: "Home Supply",
    4121: "Taxi/Rideshare",
}

USE_CHIP_VALUES = ["Chip Transaction", "Online Transaction", "Swipe Transaction"]

ERROR_VALUES = [
    None,
    "Insufficient Balance",
    "Technical Glitch",
    "Bad PIN",
    "Bad Card Number",
]

# ---------------------------------------------------------------------------
# International geography
# ---------------------------------------------------------------------------
# Each country has: full name, Faker locale, regions/provinces/states,
# representative cities per region, postal code format, and a transaction
# weight (approximate share of generated transactions).
# ---------------------------------------------------------------------------

COUNTRIES = {
    # --- North America ---
    "US": {
        "name": "United States",
        "locale": "en_US",
        "weight": 0.30,
        "regions": {
            "CA": ["Los Angeles", "San Francisco", "San Diego", "Sacramento"],
            "TX": ["Houston", "Dallas", "Austin", "San Antonio"],
            "NY": ["New York", "Buffalo", "Albany", "Rochester"],
            "FL": ["Miami", "Orlando", "Tampa", "Jacksonville"],
            "IL": ["Chicago", "Springfield", "Naperville", "Aurora"],
            "PA": ["Philadelphia", "Pittsburgh", "Harrisburg", "Allentown"],
            "OH": ["Columbus", "Cleveland", "Cincinnati", "Toledo"],
            "GA": ["Atlanta", "Savannah", "Augusta", "Athens"],
            "NC": ["Charlotte", "Raleigh", "Durham", "Greensboro"],
            "MI": ["Detroit", "Grand Rapids", "Ann Arbor", "Lansing"],
            "NJ": ["Newark", "Jersey City", "Trenton", "Princeton"],
            "VA": ["Richmond", "Virginia Beach", "Norfolk", "Arlington"],
            "WA": ["Seattle", "Tacoma", "Spokane", "Bellevue"],
            "AZ": ["Phoenix", "Tucson", "Mesa", "Scottsdale"],
            "MA": ["Boston", "Worcester", "Cambridge", "Springfield"],
            "TN": ["Nashville", "Memphis", "Knoxville", "Chattanooga"],
            "IN": ["Indianapolis", "Fort Wayne", "Evansville", "Bloomington"],
            "MO": ["Kansas City", "St. Louis", "Springfield", "Columbia"],
            "MD": ["Baltimore", "Annapolis", "Bethesda", "Rockville"],
            "WI": ["Milwaukee", "Madison", "Green Bay", "Kenosha"],
            "CO": ["Denver", "Colorado Springs", "Boulder", "Fort Collins"],
            "MN": ["Minneapolis", "St. Paul", "Duluth", "Rochester"],
            "SC": ["Charleston", "Columbia", "Greenville", "Myrtle Beach"],
            "AL": ["Birmingham", "Montgomery", "Huntsville", "Mobile"],
            "LA": ["New Orleans", "Baton Rouge", "Shreveport", "Lafayette"],
            "KY": ["Louisville", "Lexington", "Bowling Green", "Covington"],
            "OR": ["Portland", "Salem", "Eugene", "Bend"],
            "OK": ["Oklahoma City", "Tulsa", "Norman", "Edmond"],
            "CT": ["Hartford", "New Haven", "Stamford", "Bridgeport"],
            "UT": ["Salt Lake City", "Provo", "Ogden", "St. George"],
            "NV": ["Las Vegas", "Reno", "Henderson", "Sparks"],
            "IA": ["Des Moines", "Cedar Rapids", "Davenport", "Iowa City"],
            "AR": ["Little Rock", "Fort Smith", "Fayetteville", "Springdale"],
            "MS": ["Jackson", "Gulfport", "Biloxi", "Hattiesburg"],
            "KS": ["Wichita", "Overland Park", "Kansas City", "Topeka"],
            "NM": ["Albuquerque", "Santa Fe", "Las Cruces", "Rio Rancho"],
            "NE": ["Omaha", "Lincoln", "Bellevue", "Grand Island"],
            "ID": ["Boise", "Meridian", "Nampa", "Idaho Falls"],
            "WV": ["Charleston", "Huntington", "Morgantown", "Parkersburg"],
            "HI": ["Honolulu", "Hilo", "Kailua", "Kaneohe"],
            "NH": ["Manchester", "Nashua", "Concord", "Dover"],
            "ME": ["Portland", "Bangor", "Lewiston", "Auburn"],
            "MT": ["Billings", "Missoula", "Great Falls", "Bozeman"],
            "RI": ["Providence", "Warwick", "Cranston", "Pawtucket"],
            "DE": ["Wilmington", "Dover", "Newark", "Middletown"],
            "SD": ["Sioux Falls", "Rapid City", "Aberdeen", "Brookings"],
            "ND": ["Fargo", "Bismarck", "Grand Forks", "Minot"],
            "AK": ["Anchorage", "Fairbanks", "Juneau", "Sitka"],
            "VT": ["Burlington", "Montpelier", "Rutland", "Barre"],
            "WY": ["Cheyenne", "Casper", "Laramie", "Gillette"],
        },
        "postal_format": "#####",
    },
    "CA": {
        "name": "Canada",
        "locale": "en_CA",
        "weight": 0.07,
        "regions": {
            "ON": ["Toronto", "Ottawa", "Mississauga", "Hamilton"],
            "QC": ["Montreal", "Quebec City", "Laval", "Gatineau"],
            "BC": ["Vancouver", "Victoria", "Surrey", "Burnaby"],
            "AB": ["Calgary", "Edmonton", "Red Deer", "Lethbridge"],
            "MB": ["Winnipeg", "Brandon", "Steinbach", "Thompson"],
            "SK": ["Saskatoon", "Regina", "Prince Albert", "Moose Jaw"],
            "NS": ["Halifax", "Dartmouth", "Sydney", "Truro"],
            "NB": ["Moncton", "Saint John", "Fredericton", "Dieppe"],
            "NL": ["St. John's", "Mount Pearl", "Corner Brook", "Gander"],
            "PE": ["Charlottetown", "Summerside", "Stratford", "Cornwall"],
        },
        "postal_format": "A#A #A#",
    },

    # --- Europe ---
    "GB": {
        "name": "United Kingdom",
        "locale": "en_GB",
        "weight": 0.06,
        "regions": {
            "ENG": ["London", "Manchester", "Birmingham", "Liverpool", "Leeds", "Bristol"],
            "SCT": ["Edinburgh", "Glasgow", "Aberdeen", "Dundee"],
            "WLS": ["Cardiff", "Swansea", "Newport", "Bangor"],
            "NIR": ["Belfast", "Derry", "Lisburn", "Newry"],
        },
        "postal_format": "AA## #AA",
    },
    "DE": {
        "name": "Germany",
        "locale": "de_DE",
        "weight": 0.05,
        "regions": {
            "BY": ["Munich", "Nuremberg", "Augsburg", "Regensburg"],
            "NW": ["Cologne", "Dusseldorf", "Dortmund", "Essen"],
            "BW": ["Stuttgart", "Mannheim", "Karlsruhe", "Freiburg"],
            "BE": ["Berlin"],
            "HH": ["Hamburg"],
            "HE": ["Frankfurt", "Wiesbaden", "Kassel", "Darmstadt"],
            "NI": ["Hanover", "Brunswick", "Oldenburg", "Osnabruck"],
            "SN": ["Dresden", "Leipzig", "Chemnitz"],
        },
        "postal_format": "#####",
    },
    "FR": {
        "name": "France",
        "locale": "fr_FR",
        "weight": 0.05,
        "regions": {
            "IDF": ["Paris", "Versailles", "Boulogne-Billancourt", "Saint-Denis"],
            "ARA": ["Lyon", "Grenoble", "Saint-Etienne", "Clermont-Ferrand"],
            "PAC": ["Marseille", "Nice", "Toulon", "Aix-en-Provence"],
            "OCC": ["Toulouse", "Montpellier", "Nimes", "Perpignan"],
            "NAQ": ["Bordeaux", "Limoges", "Poitiers", "La Rochelle"],
            "HDF": ["Lille", "Amiens", "Roubaix", "Tourcoing"],
            "GES": ["Strasbourg", "Reims", "Metz", "Nancy"],
            "BRE": ["Rennes", "Brest", "Nantes", "Saint-Malo"],
        },
        "postal_format": "#####",
    },
    "ES": {
        "name": "Spain",
        "locale": "es_ES",
        "weight": 0.03,
        "regions": {
            "MD": ["Madrid", "Alcala de Henares", "Getafe", "Leganes"],
            "CT": ["Barcelona", "Tarragona", "Girona", "Lleida"],
            "AN": ["Seville", "Malaga", "Granada", "Cordoba"],
            "VC": ["Valencia", "Alicante", "Castellon"],
            "PV": ["Bilbao", "San Sebastian", "Vitoria"],
            "GA": ["Santiago de Compostela", "Vigo", "A Coruna"],
        },
        "postal_format": "#####",
    },
    "IT": {
        "name": "Italy",
        "locale": "it_IT",
        "weight": 0.03,
        "regions": {
            "LOM": ["Milan", "Bergamo", "Brescia", "Como"],
            "LAZ": ["Rome", "Latina", "Frosinone"],
            "CAM": ["Naples", "Salerno", "Caserta"],
            "VEN": ["Venice", "Verona", "Padua", "Vicenza"],
            "PIE": ["Turin", "Novara", "Alessandria"],
            "EMR": ["Bologna", "Parma", "Modena", "Rimini"],
            "TOS": ["Florence", "Pisa", "Siena", "Livorno"],
        },
        "postal_format": "#####",
    },
    "NL": {
        "name": "Netherlands",
        "locale": "nl_NL",
        "weight": 0.02,
        "regions": {
            "NH": ["Amsterdam", "Haarlem", "Hilversum"],
            "ZH": ["Rotterdam", "The Hague", "Delft", "Leiden"],
            "NB": ["Eindhoven", "Tilburg", "Breda"],
            "UT": ["Utrecht", "Amersfoort"],
        },
        "postal_format": "#### AA",
    },
    "SE": {
        "name": "Sweden",
        "locale": "sv_SE",
        "weight": 0.01,
        "regions": {
            "ST": ["Stockholm", "Solna", "Sundbyberg"],
            "VG": ["Gothenburg", "Boras"],
            "SK": ["Malmo", "Lund", "Helsingborg"],
        },
        "postal_format": "### ##",
    },
    "PL": {
        "name": "Poland",
        "locale": "pl_PL",
        "weight": 0.02,
        "regions": {
            "MZ": ["Warsaw", "Radom", "Plock"],
            "MP": ["Krakow", "Tarnow", "Nowy Sacz"],
            "WP": ["Poznan", "Kalisz", "Gniezno"],
            "PM": ["Gdansk", "Gdynia", "Sopot"],
            "DS": ["Wroclaw", "Legnica"],
        },
        "postal_format": "##-###",
    },
    "CH": {
        "name": "Switzerland",
        "locale": "de_CH",
        "weight": 0.01,
        "regions": {
            "ZH": ["Zurich", "Winterthur"],
            "GE": ["Geneva", "Carouge"],
            "BE": ["Bern", "Thun", "Biel"],
            "BS": ["Basel"],
        },
        "postal_format": "####",
    },
    "AT": {
        "name": "Austria",
        "locale": "de_AT",
        "weight": 0.01,
        "regions": {
            "W": ["Vienna"],
            "OO": ["Linz", "Wels", "Steyr"],
            "ST": ["Graz", "Leoben"],
            "SB": ["Salzburg", "Hallein"],
            "T": ["Innsbruck", "Kufstein"],
        },
        "postal_format": "####",
    },
    "PT": {
        "name": "Portugal",
        "locale": "pt_PT",
        "weight": 0.01,
        "regions": {
            "LIS": ["Lisbon", "Amadora", "Sintra"],
            "PRT": ["Porto", "Vila Nova de Gaia", "Matosinhos"],
            "FAR": ["Faro", "Albufeira", "Portimao"],
        },
        "postal_format": "####-###",
    },
    "IE": {
        "name": "Ireland",
        "locale": "en_IE",
        "weight": 0.01,
        "regions": {
            "D": ["Dublin", "Dun Laoghaire", "Swords"],
            "C": ["Cork", "Cobh"],
            "G": ["Galway", "Athlone"],
            "L": ["Limerick", "Ennis"],
        },
        "postal_format": "A## A#A#",
    },
    "NO": {
        "name": "Norway",
        "locale": "no_NO",
        "weight": 0.01,
        "regions": {
            "OSL": ["Oslo", "Baerum", "Asker"],
            "VES": ["Bergen", "Stavanger", "Haugesund"],
            "TRD": ["Trondheim", "Steinkjer"],
        },
        "postal_format": "####",
    },
    "DK": {
        "name": "Denmark",
        "locale": "da_DK",
        "weight": 0.01,
        "regions": {
            "HOV": ["Copenhagen", "Frederiksberg", "Glostrup"],
            "MJY": ["Aarhus", "Viborg", "Herning"],
            "SDN": ["Odense", "Esbjerg", "Kolding"],
        },
        "postal_format": "####",
    },
    "FI": {
        "name": "Finland",
        "locale": "fi_FI",
        "weight": 0.01,
        "regions": {
            "UUS": ["Helsinki", "Espoo", "Vantaa"],
            "PIR": ["Tampere", "Nokia"],
            "VSU": ["Turku", "Pori", "Rauma"],
        },
        "postal_format": "#####",
    },
    "CZ": {
        "name": "Czech Republic",
        "locale": "cs_CZ",
        "weight": 0.01,
        "regions": {
            "PR": ["Prague"],
            "JM": ["Brno", "Znojmo"],
            "MS": ["Ostrava", "Opava"],
            "PL": ["Plzen", "Klatovy"],
        },
        "postal_format": "### ##",
    },
    "GR": {
        "name": "Greece",
        "locale": "el_GR",
        "weight": 0.01,
        "regions": {
            "AT": ["Athens", "Piraeus", "Glyfada"],
            "TH": ["Thessaloniki", "Kavala"],
            "CR": ["Heraklion", "Chania", "Rethymno"],
        },
        "postal_format": "### ##",
    },
    "RO": {
        "name": "Romania",
        "locale": "ro_RO",
        "weight": 0.01,
        "regions": {
            "B": ["Bucharest"],
            "CJ": ["Cluj-Napoca", "Turda"],
            "TM": ["Timisoara", "Lugoj"],
            "IS": ["Iasi", "Pascani"],
        },
        "postal_format": "######",
    },
    "HU": {
        "name": "Hungary",
        "locale": "hu_HU",
        "weight": 0.01,
        "regions": {
            "BU": ["Budapest"],
            "DE": ["Debrecen", "Hajduszoboszlo"],
            "GS": ["Gyor", "Sopron"],
            "PE": ["Pecs", "Mohacs"],
        },
        "postal_format": "####",
    },
    "BE": {
        "name": "Belgium",
        "locale": "nl_BE",
        "weight": 0.01,
        "regions": {
            "BRU": ["Brussels", "Ixelles", "Schaerbeek"],
            "ANT": ["Antwerp", "Mechelen"],
            "VLG": ["Ghent", "Bruges", "Leuven"],
            "WAL": ["Liege", "Namur", "Charleroi"],
        },
        "postal_format": "####",
    },

    # --- South America ---
    "BR": {
        "name": "Brazil",
        "locale": "pt_BR",
        "weight": 0.04,
        "regions": {
            "SP": ["Sao Paulo", "Campinas", "Santos", "Guarulhos"],
            "RJ": ["Rio de Janeiro", "Niteroi", "Petropolis"],
            "MG": ["Belo Horizonte", "Uberlandia", "Juiz de Fora"],
            "BA": ["Salvador", "Feira de Santana"],
            "RS": ["Porto Alegre", "Caxias do Sul", "Pelotas"],
            "PR": ["Curitiba", "Londrina", "Maringa"],
            "PE": ["Recife", "Olinda", "Caruaru"],
            "CE": ["Fortaleza", "Sobral"],
        },
        "postal_format": "#####-###",
    },
    "AR": {
        "name": "Argentina",
        "locale": "es_AR",
        "weight": 0.02,
        "regions": {
            "BA": ["Buenos Aires", "La Plata", "Mar del Plata"],
            "CO": ["Cordoba", "Villa Carlos Paz"],
            "SF": ["Rosario", "Santa Fe"],
            "MZ": ["Mendoza", "San Rafael"],
            "TU": ["San Miguel de Tucuman"],
        },
        "postal_format": "A####AAA",
    },
    "CO": {
        "name": "Colombia",
        "locale": "es_CO",
        "weight": 0.01,
        "regions": {
            "DC": ["Bogota"],
            "ANT": ["Medellin", "Envigado"],
            "VAC": ["Cali", "Palmira"],
            "ATL": ["Barranquilla", "Soledad"],
        },
        "postal_format": "######",
    },
    "CL": {
        "name": "Chile",
        "locale": "es_CL",
        "weight": 0.01,
        "regions": {
            "RM": ["Santiago", "Puente Alto", "Maipu"],
            "VA": ["Valparaiso", "Vina del Mar"],
            "BI": ["Concepcion", "Talcahuano"],
        },
        "postal_format": "#######",
    },
    "PE": {
        "name": "Peru",
        "locale": "es",
        "weight": 0.01,
        "regions": {
            "LIM": ["Lima", "Callao", "San Isidro"],
            "AQP": ["Arequipa"],
            "CUS": ["Cusco"],
            "LAL": ["Trujillo", "Chiclayo"],
        },
        "postal_format": "#####",
    },
    "EC": {
        "name": "Ecuador",
        "locale": "es",
        "weight": 0.005,
        "regions": {
            "P": ["Quito", "Sangolqui"],
            "G": ["Guayaquil", "Duran"],
            "A": ["Cuenca", "Azogues"],
        },
        "postal_format": "######",
    },
    "UY": {
        "name": "Uruguay",
        "locale": "es",
        "weight": 0.005,
        "regions": {
            "MO": ["Montevideo"],
            "MA": ["Punta del Este", "Maldonado"],
            "CO": ["Colonia del Sacramento"],
        },
        "postal_format": "#####",
    },

    # --- Asia ---
    "JP": {
        "name": "Japan",
        "locale": "ja_JP",
        "weight": 0.06,
        "regions": {
            "TK": ["Tokyo", "Shibuya", "Shinjuku", "Akihabara"],
            "OS": ["Osaka", "Sakai", "Higashiosaka"],
            "KN": ["Yokohama", "Kawasaki", "Kamakura"],
            "AI": ["Nagoya", "Toyota", "Okazaki"],
            "KY": ["Kyoto", "Uji"],
            "HK": ["Sapporo", "Hakodate", "Asahikawa"],
            "FK": ["Fukuoka", "Kitakyushu", "Kumamoto"],
            "HR": ["Hiroshima", "Kure"],
        },
        "postal_format": "###-####",
    },
    "CN": {
        "name": "China",
        "locale": "zh_CN",
        "weight": 0.06,
        "regions": {
            "BJ": ["Beijing", "Haidian", "Chaoyang"],
            "SH": ["Shanghai", "Pudong", "Jing'an"],
            "GD": ["Guangzhou", "Shenzhen", "Dongguan", "Foshan"],
            "ZJ": ["Hangzhou", "Ningbo", "Wenzhou"],
            "JS": ["Nanjing", "Suzhou", "Wuxi"],
            "SC": ["Chengdu", "Chongqing", "Mianyang"],
            "HB": ["Wuhan", "Yichang"],
            "SD": ["Qingdao", "Jinan", "Yantai"],
        },
        "postal_format": "######",
    },

    # --- Russia ---
    "RU": {
        "name": "Russia",
        "locale": "ru_RU",
        "weight": 0.05,
        "regions": {
            "MOW": ["Moscow", "Zelenograd", "Khimki"],
            "SPE": ["Saint Petersburg", "Pushkin", "Peterhof"],
            "NSK": ["Novosibirsk", "Berdsk"],
            "SVE": ["Yekaterinburg", "Nizhny Tagil"],
            "KDA": ["Krasnodar", "Sochi", "Novorossiysk"],
            "TAT": ["Kazan", "Naberezhnye Chelny"],
            "SAM": ["Samara", "Tolyatti"],
            "RST": ["Rostov-on-Don", "Taganrog"],
        },
        "postal_format": "######",
    },
}

# Flat list of all country codes for convenience
ALL_COUNTRIES = list(COUNTRIES.keys())

# Legacy alias — some downstream code may still reference US_STATES
US_STATES = list(COUNTRIES["US"]["regions"].keys())
