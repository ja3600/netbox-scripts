from django.utils.text import slugify

from dcim.models import SiteGroup, Device, RackRole, Site, Location, Rack
from extras.scripts import *


class MyScript(Script):
    
    class Meta:
        name = "Add a new rack to Field Office"
        description = "Creates an MDF rack called A.1 if one does not already exists and then puts the router and switch in it."
        commit_default = False

    site_code = StringVar(
        description="To only add a rack to just one site, enter the site Facility code",
        required=False
    )

    def run(self, data, commit):

        rack_role = RackRole.objects.get(name='Mix Use')
        site_code = data['site_code']

        if site_code:
            # just do one site
            site = Site.objects.get(facility=site_code.upper())
            self.log_info(f"Will add a rack to one site: {site}")

            if len(site.racks.all()) > 0:
                self.log_warning(f"Skipping..{site} already has a rack.")
            else:
                rack_location = Location(
                    name=f"MDF Room",
                    slug=slugify(f"MDF Room"),
                    site=site,
                )
                rack_location.save()
                self.log_success(f"Created rack location: {rack_location}")

                # create the rack 
                rack = Rack(
                    name=f"A.1",
                    site=site,
                    role=rack_role,
                    location=rack_location,
                )
                rack.save()
                self.log_success(f"Created rack: {rack}")

                router = Device.objects.get(name=f"{site_code.upper()}RA")
                switch = Device.objects.get(name=f"{site_code.upper()}S01A")

                self.log_info(f"Placing these devices in rack {rack}: {router}, {switch}")

                # place devices in the rack
                router.rack=rack
                router.position=25
                router.face="front"
                router.save()

                switch.rack=rack
                switch.position=23
                switch.face="front"
                switch.save()


        else:
            parent = SiteGroup.objects.filter(parent__name="Field Office")
            #many_sites = Site.objects.filter(group=1)
            self.log_info(f"Looping through {len(parent)} site groups under parent Field Office")
            
            for children in parent:
                for site in Site.objects.filter(group=children, status='active'):

                    self.log_info(f"group: {children}  site: {site}")

                    if len(site.racks.all()) > 0:
                        self.log_warning(f"Skipping..{site} already has a rack.")
                    else:
                        rack_location = Location(
                            name=f"MDF Room",
                            slug=slugify(f"MDF Room"),
                            site=site,
                        )
                        rack_location.save()
                        self.log_success(f"Created rack location: {rack_location}")

                        # create the MDF rack 
                        rack = Rack(
                            name=f"A.1",
                            site=site,
                            role=rack_role,
                            location=rack_location,
                        )
                        rack.save()
                        self.log_success(f"Created rack: {rack}")

                        site_code = site.facility.upper()

                        self.log_info(f"Looking up these devices: {site_code}RA, {site_code}S01A")

                        if len(Device.objects.filter(site=site)) > 0:

                            router = Device.objects.get(name=f"{site_code}RA")
                            switch = Device.objects.get(name=f"{site_code}S01A")
                            self.log_info(f"Placing these devices in rack {rack}: {router}, {switch}")

                            # place devices in the rack
                            router.rack=rack
                            router.position=25
                            router.face="front"
                            router.save()

                            switch.rack=rack
                            switch.position=23
                            switch.face="front"
                            switch.save()
