import json
from asgiref.sync import sync_to_async
from django.http import JsonResponse
from .models import Record
from .logic import create_record, snapshot, crud_cycle

def health(request):
    return JsonResponse({"ready": True})

def items(request, pk=None):
    if request.method == "POST" and pk is None:
        body = json.loads(request.body)
        return JsonResponse(snapshot(create_record(body["token"])), status=201)
    if pk is None:
        return JsonResponse({"error": "method"}, status=405)
    try:
        obj = Record.objects.get(pk=pk)
    except Record.DoesNotExist:
        return JsonResponse({"error": "missing"}, status=404)
    if request.method == "GET":
        return JsonResponse(snapshot(obj))
    if request.method == "PUT":
        obj.counter = int(json.loads(request.body)["counter"])
        obj.save(update_fields=["counter"])
        return JsonResponse(snapshot(obj))
    if request.method == "DELETE":
        obj.delete()
        return JsonResponse({"deleted": True})
    return JsonResponse({"error": "method"}, status=405)

async def async_cycle(request):
    token = json.loads(request.body)["token"]
    result = await sync_to_async(crud_cycle, thread_sensitive=True)(token)
    return JsonResponse(result)
