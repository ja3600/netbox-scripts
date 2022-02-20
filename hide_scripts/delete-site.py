from django.utils.text import slugify

from dcim.models import Device, Site, Rack
from extras.scripts import *


class MyScript(Script):
    
    class Meta:
        name = "Delete a site"
        description = "This script will completely wipe out a site. Use with extreme caution!"
        field_order = ['site_to_delete']
        commit_default = False

    site_to_delete = ObjectVar(
        description="Sites",
        model=Site,
        #display_field='name',
    )

    def run(self, data, commit):

        site = data['site_to_delete']

        for device in Device.objects.filter(site=site):
            self.log_info(f"Deleted {device.delete()}")
        
        for racks in Rack.objects.filter(site=site):
            self.log_info(f"Deleted {racks.delete()}")

        self.log_info(f"Deleted {site.delete()}")


 
 
