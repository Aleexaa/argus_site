from django.shortcuts import render
from django.http import HttpResponse

def partners_simple(request):
    return HttpResponse("ПАРТНЕРЫ ПРОСТАЯ ВЕРСИЯ РАБОТАЕТ!")