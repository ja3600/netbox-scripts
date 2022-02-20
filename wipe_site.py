from django.utils.text import slugify


from extras.scripts import *
from dcim.choices import DeviceStatusChoices, SiteStatusChoices, LinkStatusChoices
from tenancy.models import Tenant
from dcim.models import Site, Location, Rack, RackRole
from dcim.models import Device, DeviceRole, DeviceType, Interface, Cable
from circuits.models import Circuit, CircuitType, CircuitTermination, ProviderNetwork, Provider
from extras.scripts import *

class MyScript(Script):
    
    class Meta:
        name = "Wipe site"
        description = "This script will completely wipe out a site and its circuits!!"
        field_order = ['site_to_delete']
        commit_default = False

    site_to_delete = ObjectVar(
        description="Sites",
        model=Site,
        #display_field='name',
    )

    def run(self, data, commit):

        def WipeSite(site):
            '''
            WARNING: This deletes the site matching site name.
            '''
            # alternate means to lookup up sites
            # sites = Site.objects.filter(name__contains=name_contains).all()
            
            for device in Device.objects.filter(site=site):
                self.log_debug(f"Deleted {device.delete()}")
            
            for racks in Rack.objects.filter(site=site):
                self.log_debug(f"Deleted {racks.delete()}")

            for racks in Rack.objects.filter(site=site):
                self.log_debug(f"Deleted {racks.delete()}")

            ct = CircuitTermination.objects.filter(site=site, term_side='A').all()
            for ct_item in ct:
                circuit_to_delete = Circuit.objects.get(cid=ct_item.circuit)
                self.log_debug(f"Deleted {circuit_to_delete.delete()}")

            self.log_warning(f"{site.delete()} was deleted!")

            return


        WipeSite(data['site_to_delete'])


