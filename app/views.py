from django.shortcuts import render
import methods
from django.http import HttpResponseRedirect
from datetime import datetime
from django import forms

# Create your views here.
class LocationForm(forms.Form):
    origin = forms.CharField(label="Start Location", max_length=100)
    dest = forms.CharField(label="End Location", max_length=100)

def ping(request):
    current_coords = tuple([1.3499, 103.8734])
    trip_in_progress, completed_legs, current_leg, dest_coords, current_coords = methods.read_trip()

    # if this is a POST request we need to process the form data
    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = LocationForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            current_coords = methods.search_location(form.cleaned_data['origin'])
            dest_coords = methods.search_location(form.cleaned_data['dest'])
            trip_in_progress = True
            methods.update_trip(trip_in_progress, dest_coords=dest_coords, current_coords=current_coords)
            return HttpResponseRedirect("/app/route/")

    # if a GET (or any other method) we'll create a blank form
    else:
        form = LocationForm()

    return render(request, "home.html", {'form':form})

def route(request):
    trip_in_progress, completed_legs, current_leg, dest_coords, current_coords = methods.read_trip()
    now = datetime.now()
    date = now.strftime("%m-%d-%Y")
    time = now.strftime("%H:%M:%S")
    recs = methods.check_new(trip_in_progress, current_leg, current_coords, dest_coords, date, time)
    try:
        time1 = recs['route0']['durations'][0]
    except:
        time1 = -1
    try:
        time2 = recs['route1']['durations'][0]
    except:
        time2 = -1

    try:
        time3 = recs['route2']['durations'][0]
    except:
        time3 = -1

    return render(request, 'route.html', {'time1': time1, 'time2': time2, 'time3': time3})