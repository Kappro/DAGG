import requests
import math
import pickle
import json

def search_location(search):
    url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={search}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
    with open("a.pickle", "rb") as infile:
        tokens = pickle.load(infile)
    auth = tokens['onemap']
    headers = {"Authorization": auth}
    response = requests.request("GET", url, headers=headers).json()
    first_res = response['results'][0]

    lat = first_res['LATITUDE']
    long = first_res['LONGITUDE']

    return tuple([lat, long])

def fetch_route(auth, start_lat, start_long, end_lat, end_long,
                date, hour, minutes, seconds,
                route_type="pt", mode="TRANSIT",
                max_walk=-1, num_itin=3):
    start_loc = f"{str(start_lat)}%2C{str(start_long)}"
    end_loc = f"{str(end_lat)}%2C{str(end_long)}"
    time = f"{hour}%3A{minutes}%3A{seconds}"

    url = f"https://www.onemap.gov.sg/api/public/routingsvc/route?start={start_loc}&end={end_loc}&routeType={route_type}&date={date}&time={time}&mode={mode}"
    if max_walk>-1:
        url += f"&maxWalkDistance={str(max_walk)}"
    if num_itin>0 and num_itin<4:
        url += f"&numItineraries={str(num_itin)}"

    headers = {"Authorization": auth}

    response = requests.request("GET", url, headers=headers)

    return response.json()

def convert_seat(seats):
    new = seats.copy()

    for i in range(len(new)):
        if new[i]=="SEA":
            new[i] = 0
        elif new[i]=="SDA":
            new[i] = 1
        elif new[i]=="LSD":
            new[i] = 2

    return new

def check_arrival(current, destination):
    lat_min = destination[0]-0.005
    lat_max = destination[0]+0.005
    long_min = destination[1] - 0.005
    long_max = destination[1] + 0.005

    if lat_min<current[0] and current[0]<lat_max:
        if long_min<current[1] and current[1]<long_max:
            return True

    return False


def check_bus(auth, stop_id, service_no):
    url = f"http://datamall2.mytransport.sg/ltaodataservice/BusArrivalv2?BusStopCode={stop_id}"

    payload = {}
    headers = {
        'AccountKey': auth
    }

    response = requests.request("GET", url, headers=headers, data=payload).json()

    service = []
    for svc in response['Services']:
        if svc['ServiceNo']==service_no or service_no=='all':
            service.append(svc)

    if(len(service)==0):
        return [], []

    dur = []
    seats = []

    arr_time1 = service[0]['NextBus']['EstimatedArrival'].strip("T")[1].strip("+")[0].strip(":")
    try:
        duration1 = 0
        dur.append(duration1)
        seats.append(service[0]['NextBus']['Load'])
    except:
        return [], []

    try:
        arr_time2 = service[0]['NextBus2']['EstimatedArrival'].strip("T")[1].strip("+")[0].strip(":")
        duration2 = math.ceil((arr_time2[0]-arr_time1[0])*60 + (arr_time2[1]-arr_time1[1]) + (arr_time2[2]-arr_time1[2])/60)
        dur.append(duration2)
        seats.append(service[0]['NextBus2']['Load'])
    except:
        pass

    try:
        arr_time3 = service[0]['NextBus3']['EstimatedArrival'].strip("T")[1].strip("+")[0].strip(":")
        duration3 = math.ceil((arr_time3[0]-arr_time1[0])*60 + (arr_time3[1]-arr_time1[1]) + (arr_time3[2]-arr_time1[2])/60)
        dur.append(duration3)
        seats.append(service[0]['NextBus3']['Load'])
    except:
        pass

    seats = convert_seat(seats)

    return seats, dur

def check_train_traffic(auth, station):
    url = "http://datamall2.mytransport.sg/ltaodataservice/PCDRealTime?TrainLine="
    station_line = ''
    station_line = station_line + station[0] + station[1]
    if station_line == 'SW' or station_line == 'SE':
        station_line = 'SLRT'
    elif station_line == 'PW' or station_line == 'PE':
        station_line = 'PLRT'
    else:
        station_line = station_line + 'L'
    new_url = url + station_line
    payload = {}
    headers = {
        'AccountKey': auth
    }

    response = requests.request("GET", new_url, headers=headers, data=payload).json()
    potato = response['value']
    for i in potato:
        if(i['Station'] == station):
            if(i['CrowdLevel'] == 'l'):
                return 0
            elif (i['CrowdLevel'] == 'm'):
                return 1
            elif (i['CrowdLevel'] == 'h'):
                return 2
            else:
                return -1

def get_next_stop(current_leg):
    dest = current_leg['to']
    return dest['stopCode'], dest['lat'], dest['lon']

def get_first_transit_leg(route):
    legs = route['legs']
    if len(legs)==1:
        return legs[0]
    i = 0
    if legs[0]['mode'] == 'WALK':
        i += 1
    return legs[i]

def get_route_optimality(auth, route):
    durations = [route['duration']]
    densities = []

    first_transit_leg = get_first_transit_leg(route)
    if first_transit_leg==None:
        return durations, 'WALK', {}
    first_mode = first_transit_leg['mode']

    if first_mode == 'SUBWAY':
        densities.append(check_train_traffic(auth, first_transit_leg['from']['stopCode']))
        durations[0] += densities[0]*60

    elif first_mode == 'BUS':
        seats, durs = check_bus(auth, first_transit_leg['from']['stopCode'], first_transit_leg['route'])
        dur = durations[0]
        durations.pop()
        for i in range(len(seats)):
            densities.append(seats[i])
            durations.append(dur+durs[i])

    return durations, first_mode, densities

def return_leg_instructions(leg):
    if leg['mode']=='WALK':
        return f"Walk to {leg['to']['name']}."
    elif leg['mode']=='SUBWAY':
        return f"Take the train from {leg['from']['name']} to {leg['to']['name']}."
    else:
        return f"Take the bus from {leg['from']['name']} to {leg['to']['name']}."

def return_recommendations(auth, recs):
    routes = {}
    for i in range(len(recs)):
        route_details = {}
        durations, first_mode, densities = get_route_optimality(auth, recs[i])
        pt = 0
        for j in recs[i]['legs']:
            if j['mode']!='WALK':
                pt += 1
        route_details['transfers_left'] = pt
        route_details['density'] = densities
        route_details['next_mode'] = first_mode
        route_details['next_step'] = return_leg_instructions(get_first_transit_leg(recs[i]))
        route_details['durations'] = durations
        routes[f"route{str(i)}"] = route_details

    return routes

def check_new(trip_in_progress, current_leg, current_coords, dest_coords, date, time):
    with open("a.pickle", "rb") as infile:
        tokens = pickle.load(infile)

    om_token = tokens['onemap']
    ltadm_token = tokens['ltadm']

    time_list = time.split(":")

    if not trip_in_progress or current_leg is None:
        response = fetch_route(om_token, start_lat=current_coords[0], start_long=current_coords[1],
                               end_lat=dest_coords[0], end_long=dest_coords[1],
                               date=date, hour=time_list[0], minutes=time_list[1], seconds=time_list[2])

        recs = response['plan']['itineraries']
        return return_recommendations(ltadm_token, recs)

    else:
        next_checkpoint = tuple([current_leg['to']['lat'], current_leg['to']['lon']])
        if check_arrival(current_coords, next_checkpoint):
            return None
        else:
            response = fetch_route(om_token, start_lat=next_checkpoint[0], start_long=next_checkpoint[1],
                                   end_lat=dest_coords[0], end_long=dest_coords[1],
                                   date=date, hour=time_list[0], minutes=time_list[1], seconds=time_list[2])
            recs = response['plan']['itineraries']
            return return_recommendations(ltadm_token, recs)

def select_route(route):
    if len(route['legs'])==1:
        return route[0], None
    elif not route['legs'][0]['mode']=='WALK':
        return None, route[0]
    else:
        return route[0], route[1]

def update_trip(trip_in_progress, completed_legs=None, current_leg=None, dest_coords=None, current_coords=tuple([1.3499, 103.8734])):
    with open('data/b.json', 'w+', encoding='utf-8') as file_handle:
        json.dump({
            'trip_in_progress': trip_in_progress,
            'completed_legs': completed_legs,
            'current_leg': current_leg,
            'dest_coords': dest_coords,
            'current_coords': current_coords
        }, file_handle, indent=4)

def read_trip():
    try:
        with open('data/b.json', 'r', encoding='utf-8') as file_handle:
            trip_details = json.load(file_handle)
    except:
        trip_in_progress = False
        completed_legs = None
        current_leg = None
        dest_coords = None
        current_coords = None
        return trip_in_progress, completed_legs, current_leg, dest_coords, current_coords
    return trip_details['trip_in_progress'], trip_details['completed_legs'], trip_details['current_leg'], trip_details['dest_coords'], trip_details['current_coords']
