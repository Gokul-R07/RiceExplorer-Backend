
from django.core.exceptions import BadRequest
from django.http import FileResponse
import ee
from .data_processing import compute_feature, filter_dataset, make_false_color_monthly_composite
from .conversion import geojson_to_ee, shp_to_ee, shp_zip_to_ee
from .constants import DATASET_LIST, FEATURE_LIST, MODEL_LIST
from .speckle_filters import boxcar
import base64
import requests

# Initialize the Earth Engine API
# ee.Initialize()
seasons = ['sowing', 'peak', 'harvesting'] 

# default_boundary_file = "data/Terai_belt_Nepal.shp"
default_boundary_file = "data/TAMIL NADU_DISTRICTS.geojson"
# default_boundary_file = "data/TAMIL NADU_DISTRICTS-full.geojson"
# default_boundary_file = "data/TamilNadu.geojson"

default_download_scale = 250

rice_vis_params = {"min": 0, "max": 1, "opacity": 1, "palette": ["ffffff", "328138"]}

rice_thumbnail_params = {"min": 0, "max": 2, "opacity": 1, "palette": ["000000", "328138", "ffffff"]}

districts={
    
  "Ariyalur": {"latitude": 11.0767, "longitude": 79.1178},
  "Chengalpattu": {"latitude": 12.6847, "longitude": 79.9836},
  "Chennai": {"latitude": 13.0827, "longitude": 80.2707},
  "Coimbatore": {"latitude": 11.0168, "longitude": 76.9558},
  "Cuddalore": {"latitude": 11.7569, "longitude": 79.7503},
  "Dharmapuri": {"latitude": 12.0967, "longitude": 78.1935},
  "Dindigul": {"latitude": 10.3673, "longitude": 77.9803},
  "Erode": {"latitude": 11.3428, "longitude": 77.7274},
  "Kallakurichi": {"latitude": 11.7381, "longitude": 78.9637},
  "Kanchipuram": {"latitude": 12.8362, "longitude": 79.7041},
  "Kanyakumari": {"latitude": 8.0873, "longitude": 77.5385},
  "Karur": {"latitude": 10.9506, "longitude": 78.0810},
  "Krishnagiri": {"latitude": 12.5186, "longitude": 78.2132},
  "Madurai": {"latitude": 9.9252, "longitude": 78.1198},
  "Mayiladuthurai": {"latitude": 11.1085, "longitude": 79.6565},
  "Nagapattinam": {"latitude": 10.8050, "longitude": 79.8428},
  "Namakkal": {"latitude": 11.2190, "longitude": 78.1620},
  "Nilgiris": {"latitude": 11.4007, "longitude": 76.7000},
  "Perambalur": {"latitude": 11.2290, "longitude": 78.8755},
  "Pudukkottai": {"latitude": 10.3830, "longitude": 78.8160},
  "Ramanathapuram": {"latitude": 9.3695, "longitude": 78.8299},
  "Ranipet": {"latitude": 12.9266, "longitude": 79.3330},
  "Salem": {"latitude": 11.6643, "longitude": 78.1460},
  "Sivaganga": {"latitude": 9.8489, "longitude": 78.4876},
  "Tenkasi": {"latitude": 8.9580, "longitude": 77.3124},
  "Thanjavur": {"latitude": 10.7860, "longitude": 79.1378},
  "Theni": {"latitude": 10.0112, "longitude": 77.4753},
  "Thoothukudi": {"latitude": 8.7832, "longitude": 78.1348},
  "Tiruchirappalli": {"latitude": 10.7905, "longitude": 78.7047},
  "Tirunelveli": {"latitude": 8.7139, "longitude": 77.7567},
  "Tirupathur": {"latitude": 12.4892, "longitude": 78.5724},
  "Tiruppur": {"latitude": 11.1107, "longitude": 77.3407},
  "Tiruvallur": {"latitude": 13.1394, "longitude": 79.9073},
  "Tiruvannamalai": {"latitude": 12.2296, "longitude": 79.0661},
  "Tiruvarur": {"latitude": 10.7745, "longitude": 79.6320},
  "Vellore": {"latitude": 12.9165, "longitude": 79.1325},
  "Viluppuram": {"latitude": 11.9139, "longitude": 79.5079},
  "Virudhunagar": {"latitude": 9.5896, "longitude": 77.9515}
}




    
def calculate_thresholds(json_data):
    
    try:
        dataset_name = json_data['dataset']['name']
        cloud_percentage = int(json_data['dataset']['cloud'])
        district_name = json_data['dataset']['boundary']
        start_date = json_data['seasons'][0]['start']
        end_date = json_data['seasons'][0]['end']
        coord = districts.get(district_name)

        point = ee.Geometry.Point(coord['longitude'], coord['latitude'])
        roi = point  
        dataset = ee.ImageCollection(dataset_name) \
            .filterBounds(roi) \
            .filterDate(start_date, end_date) \
            

        min_threshold = dataset.reduce(ee.Reducer.min()).reduceRegion(
            reducer=ee.Reducer.first(), 
            geometry=roi, 
            scale=10).getInfo()
        max_threshold = dataset.reduce(ee.Reducer.max()).reduceRegion(
            reducer=ee.Reducer.first(), 
            geometry=roi, 
            scale=10).getInfo()
        print(min_threshold)

        return min_threshold, max_threshold

    except Exception as e:
        print("Error:", e)
        return None, None


def get_phenology(data):
    '''
    Get time-series image data for the input ground truth samples
    '''
    # print(data)
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    
    data_filters = data['dataset']
    samples = data['samples']
    
    start_date = datetime.strptime(data['phenology_dates']['start_date'], '%Y-%m')
    end_date = datetime.strptime(data['phenology_dates']['end_date'], '%Y-%m')+relativedelta(months=+1)
    
    samples_ee = geojson_to_ee(samples) 
    
    data_pool = filter_dataset(data_filters, samples_ee.geometry()) \
                .filterDate(start_date.strftime("%Y-%m"), end_date.strftime("%Y-%m"))
    
    composite = make_composite(data_pool, \
                               start_date.strftime("%Y-%m"), \
                               end_date.strftime("%Y-%m"), \
                               int(data_filters['composite_days']), \
                               data_filters['composite'])
    
    feature_pool = compute_feature(data_filters['name'], composite, data_filters['feature'])

    year_img = feature_pool.map(lambda img: img.unmask(99999).rename(ee.Number(img.get('system:time_start')).format("%d").cat('_feature'))) \
                            .toBands()
    
    sample_res = year_img.sampleRegions(
        samples_ee,
        scale=10,
        geometries=True
    )
    
    return sample_res.getInfo()

def get_monthly_composite(start_date, end_date):
    return make_false_color_monthly_composite(start_date, end_date)

def make_composite(data_pool: ee.ImageCollection, start_date, end_date, days, method="median") -> ee.ImageCollection:
    
    def getComposite(date):
        date = ee.Date(date)
        end_millis = date.advance(days, "day").millis().min(ee.Date(end_date).millis()) 
        filtered_pool = data_pool.filterDate(date, ee.Date(end_millis))
        
        if method == 'minimum':
            season_data = filtered_pool.min()
        elif method == 'maximum':
            season_data = filtered_pool.max()
        elif method == 'median':
            season_data = filtered_pool.median()
        elif method == 'mean':
            season_data = filtered_pool.mean()
        elif method == 'mode':
            season_data = filtered_pool.mode()
        else:
            raise BadRequest("Unrecognized composite type")
        
        return ee.Algorithms.If(filtered_pool.size().gt(0), season_data.set('system:time_start', date.millis()))
    
    def map_func(dateMillis):
        date = ee.Date(dateMillis)
        return getComposite(date)
    
    
    gap_difference = ee.Date(start_date).advance(days, 'day').millis().subtract(ee.Date(start_date).millis())
    list_map = ee.List.sequence(ee.Date(start_date).millis(), ee.Date(end_date).millis(), gap_difference)
    composites = ee.ImageCollection.fromImages(list_map.map(map_func).removeAll([None]))
    
    return composites

def compute_hectare_area(img, band_name, boundary, scale) -> ee.Number:
    area = ee.Number(img.multiply(ee.Image.pixelArea()).reduceRegion(ee.Reducer.sum(),boundary,scale,None,None,False,1e13).get(band_name)).divide(1e4).getInfo()
    return area

def run_threshold_based_classification(filters):
   
    print(filters)
    
    data_filters = filters['dataset']
    if data_filters['boundary'] == 'upload':
        boundary = shp_zip_to_ee(data_filters['boundary_file'])
    else:
        default_boundary = shp_to_ee(default_boundary_file)
        boundary = ee.Feature(default_boundary.filterMetadata('DISTRICT', 'equals', data_filters['boundary']).first())
    crop_mask = ee.Image(1)
    if data_filters["use_crop_mask"]:
        if data_filters["crop_mask"]:
            crop_mask = ee.Image(data_filters["crop_mask"]).clip(boundary)
        else:
            raise BadRequest("Invalid crop mask argument.")
    
    pool = filter_dataset(data_filters, boundary.geometry())
    
    op = filters['op']
    season_filters = filters['seasons']
    season_res = {season['name']: None for season in season_filters}
    
    def map_composites(composite):
        composite = ee.Image(composite)
        return (composite.lte(thres_max)) \
            .And(composite.gte(thres_min)) \
            .updateMask(crop_mask).clip(boundary)

    for season in season_filters:
            
        start_date, end_date = season['start'], season['end']
        
        thres_min, thres_max = float(season['min']), float(season['max'])

        season_data_pool = pool.filter(ee.Filter.date(start_date, end_date))
        
  
        if data_filters['name'] in DATASET_LIST['radar']:
            season_data_pool = season_data_pool \
                .map(lambda img: boxcar(img))

        season_data_pool = compute_feature(data_filters['name'], season_data_pool, data_filters['feature'])
        
        composites = make_composite(season_data_pool, start_date, end_date, days=int(data_filters["composite_days"]), method=data_filters['composite'])
        
    
        thresholded_composites = composites.map(map_composites)
        
        season_res[season['name']] = thresholded_composites.Or()
        

    season_res_list = list(season_res.values())
    combined_res = season_res_list[0]
    for i in range(1, len(season_res_list)):
        if op == 'and':
            combined_res = combined_res.And(season_res_list[i])
        else:
            combined_res = combined_res.Or(season_res_list[i])
    
    if data_filters['name'] in DATASET_LIST['radar']:
        scale = DATASET_LIST['radar'][data_filters['name']]['scale']
    else:
        scale = DATASET_LIST['optical'][data_filters['name']]['scale']
        
    return combined_res, boundary, scale

def make_empirical_results(img, boundary, scale):
    
    res = {}
    
    area = compute_hectare_area(img, 'feature', boundary.geometry(), scale)
    
    thumbnail_img = img.unmask(2)
        
    res['combined'] = {
        'tile_url': img.getMapId(rice_vis_params)['tile_fetcher'].url_format,
        'download_url': thumbnail_img.getThumbURL({
            **rice_thumbnail_params,           # the style for thumbnail picture
            'dimensions': 1920,
            'region': boundary.geometry(),
            'format': 'jpg'
        }),
        "area": area
    }
    
    return res

def export_result(img, boundary, scale):
    import time
        
    task = ee.batch.Export.image.toDrive(img, **{
        "description": str(time.time()),
        "region": boundary.geometry(),
        "scale": scale,
        "maxPixels": 1e13,
    })
    
    task.start()
    
    return task.status()['id']
    

def get_task_list():
    tasks = ee.batch.Task.list()
    res = []
    for task in tasks:
        res.append(task.status())
    return res

def get_the_task(id):
    tasks = ee.batch.Task.list()
    for task in tasks:
        if task.status()['id'] == id:
            return task.status()
    return None
    

def download_file(id):
    from pydrive.auth import GoogleAuth
    from pydrive.drive import GoogleDrive
    from oauth2client.service_account import ServiceAccountCredentials
    from utils.credential import EE_PRIVATE_KEY
    import json
    
    status = get_the_task(id)
    if status is None:
        return None
    
    gauth = GoogleAuth()
    scopes=['https://www.googleapis.com/auth/drive']
    # print(json.loads(EE_PRIVATE_KEY))
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(EE_PRIVATE_KEY),
        scopes=scopes
    )
    drive = GoogleDrive(gauth)
    
    file_list = drive.ListFile({'q': "'root' in parents and trashed=false"}).GetList()
    
    for file in file_list:
        
        filename = file['title']
        
        if filename == status['description'] + ".tif":

            # download file into working directory (in this case a tiff-file)
            file.GetContentFile("results/" + filename, mimetype="image/tiff")

            # delete file afterwards to keep the Drive empty
            # file.Delete()
            
            return "results/" + filename
    
    return None
    
    

CLASS_FIELD = '$class'

def run_supervised_classification(filters, samples):
    print(filters)
    
    dataset_filters = filters['dataset']
    classification_filters = filters['classification']
    
    start_date, end_date = classification_filters['start_date'], \
                            classification_filters['end_date']
    
    # add a class property to each sample, either 0 or 1
    class_property = classification_filters['class_property']
    class_name = class_property['name']
    class_value = class_property['positiveValue']
    for feature in samples["features"]:
        if feature['properties'][class_name] == class_value:
            feature['properties'][CLASS_FIELD] = 1
        else:
            feature['properties'][CLASS_FIELD] = 0

    # try convert geojson to an ee.FeatureCollection
    samples_ee = geojson_to_ee(samples)
    
    if dataset_filters['name'] in DATASET_LIST['radar']:
        scale = DATASET_LIST['radar'][dataset_filters['name']]['scale']
    else:
        scale = DATASET_LIST['optical'][dataset_filters['name']]['scale']
    
    # boundary
    if dataset_filters['boundary'] == 'upload':
        boundary = shp_zip_to_ee(dataset_filters['boundary_file'])
    else:
        default_boundary = shp_to_ee(default_boundary_file)
        boundary = ee.Feature(
            default_boundary.filterMetadata(
                'DISTRICT', 'equals', dataset_filters['boundary']
            ).first()
        )
    
    # choosing dataset and apply filters
    pool = filter_dataset(dataset_filters, boundary.geometry()) \
            .filterDate(start_date, end_date)
            
    # speckle filter
    # TODO: allow more options for speckle filters
    if dataset_filters['name'] in DATASET_LIST['radar']:
        pool = pool.map(lambda img: boxcar(img))
    
    # compute features from raw images, e.g., NDVI, RVI, etc.
    pool = compute_feature(
        dataset_filters['name'], 
        pool, 
        dataset_filters['feature']
    )
    
    # make composite
    composites = make_composite(
        pool, 
        start_date, 
        end_date, 
        days=int(dataset_filters["composite_days"]), 
        method=dataset_filters['composite']
    )
    
    stacked_image = composites.toBands()
    
    # get image data for each sample
    points = stacked_image.sampleRegions(samples_ee, [CLASS_FIELD], scale=scale) \
                            .randomColumn() \
                            .set('band_order', stacked_image.bandNames())
    
    # train test split
    training = points.filter(ee.Filter.lt('random', classification_filters['training_ratio']))
    testing = points.filter(ee.Filter.gte('random', classification_filters['training_ratio']))
    
    # model training
    model_func = MODEL_LIST[classification_filters['model']]
    
    model_ee = model_func(**classification_filters['model_specs']) \
                .train(training, CLASS_FIELD)
                
    # evaluate model
    test_pred = testing.classify(model_ee)
    confusion_matrix = test_pred.errorMatrix(CLASS_FIELD, 'classification')
    
    # Classify the image
    classified = stacked_image.classify(model_ee)
    
    # crop mask
    crop_mask = None
    if dataset_filters["crop_mask"]:
        crop_mask = ee.Image(dataset_filters["crop_mask"]).clip(boundary.geometry())
    
    classified = classified.updateMask(crop_mask).clip(boundary.geometry())
    
    if dataset_filters['name'] in DATASET_LIST['radar']:
        scale = DATASET_LIST['radar'][dataset_filters['name']]['scale']
    else:
        scale = DATASET_LIST['optical'][dataset_filters['name']]['scale']
        
    return classified, boundary, scale, confusion_matrix


def make_classification_results(img, boundary, scale, confusion_matrix):
    
    res = {}
    
    # compute area with unit hectar
    # area = ee.Number(combined_res.multiply(ee.Image.pixelArea()).reduceRegion(ee.Reducer.sum(),boundary,scale,None,None,False,1e13).get('feature')).divide(1e4).getInfo()
    area = compute_hectare_area(img, 'classification', boundary.geometry(), scale)
    
    oa = confusion_matrix.accuracy()
    kappa = confusion_matrix.kappa()
    
    thumbnail_img = img.unmask(2)
    
    # prepare for json return
    import json
    res = {
        'classification_result': {
            'tile_url': img.getMapId(rice_vis_params)['tile_fetcher'].url_format,
            'download_url': thumbnail_img.getThumbURL({
                 **rice_thumbnail_params,           # the style for thumbnail picture
                'dimensions': 1920,
                'region': boundary.geometry(),
                'format': 'jpg'
            }),
        },
        'area': area,
        'confusion_matrix': json.dumps(confusion_matrix.getInfo()),
        'oa': oa.getInfo(),
        'kappa': kappa.getInfo(),
    }
    
    return res
    