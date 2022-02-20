from django.utils.text import slugify

from dcim.models import Device, Site, Location, Rack
from extras.scripts import *
import pandas as pd



class MyScript(Script):
    
    class Meta:
        name = "Bulk save devices in rack locations"
        description = "device and racks must already exist"
        commit_default = False

    csvfile = FileVar(
        description="Name of CSV formatted file to import",
        required=True
    )


    def run(self, data, commit):
        
        def assignRack(row):
            '''
                Function to take dataframe and use to assign rack location of device
                
                filter example to get the location ID:
                Location.objects.filter(site__name='SITENAME',name='Room 101').first()
                
            '''
            
            result = f"Processing {row['name']} at {row['rack']}"
            output = ''
            
            try:
                self.log_info(f"Looking up {row['name']} at {row['site']} in NetBox")
                
                if Device.objects.filter(name=row['name'], site__name=row['site']).count() ==1:
                    nb_device = Device.objects.filter(name=row['name'], site__name=row['site']).first()
                else:
                    raise Exception("Device query returned error")
                
                if Site.objects.filter(name=row['site']).count() == 1:
                    site = Site.objects.filter(name=row['site']).first()
                else:
                    raise Exception("Site query returned error")
                    
                self.log_success(f"Found device: {nb_device} at {site}")

                location = Location.objects.filter(
                    site__name=row['site'],
                    name=row['location']
                ).first()
                
                rack = Rack.objects.filter(
                    site__name=row['site'],
                    location__name=row['location'],
                    name=row['rack']
                ).first()

                nb_device.site = site          
                nb_device.location = location            
                nb_device.rack = rack            
                nb_device.position = row['ru_position']            
                nb_device.face = 'front'
                
                self.log_info(f"About to save {nb_device} in location {nb_device.location} rack {nb_device.rack} position {nb_device.position} ")
                nb_device.save()
                self.log_success(f"Saved {row['name']} ")
                return
                
            except Exception as err_result:
                self.log_warning(f"Skipping {row['name']} due to error ==> {err_result}")
                return err_result
                
            
        
        
        self.log_info(f"Importing file: {data['csvfile']}")
        
        self.log_info(f"Assumes all devices are racked on the front side of the the rack")

        df = pd.read_csv(data['csvfile'])
        output = []

        # self.log_info(f"Dataframe content: {df.head()}" )
        
        # this apply runs the function for each row in the dataframe
        result = df.apply(assignRack, axis='columns')
        output.append(result)
        
        return output
  
