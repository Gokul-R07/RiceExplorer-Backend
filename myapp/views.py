import json
from django.http import JsonResponse, HttpResponseBadRequest

def crop_data(request):
    try:
        selected_block = request.GET.get('block', None)
        selected_crop = request.GET.get('crop', None)
        if not selected_block or not selected_crop:
            return HttpResponseBadRequest("Both block and crop type are required.")

        with open('villages_data.json') as f:
            data = json.load(f)

       
        block_data = next((block for block in data if block['Block'] == selected_block), None)
        if not block_data:
            return JsonResponse({'message': 'Block not found', 'villages': [], 'total_area': 0})

     
        filtered_villages = [village for village in block_data['Villages'] if village['Crops'].get(selected_crop, 0) > 0]
        total_area = sum(village['Crops'].get(selected_crop, 0) for village in filtered_villages)

        response_data = {
            'villages': filtered_villages,
            'total_area': total_area
        }
        return JsonResponse(response_data)
    except Exception as e:
        return HttpResponseBadRequest(str(e))
