from django.utils.text import slugify

from dcim.choices import DeviceStatusChoices, SiteStatusChoices
from dcim.models import Cable, Device, DeviceRole, RackRole, DeviceType, Site, Location, Rack
from dcim.choices import LinkStatusChoices
from extras.scripts import *


class MyScript(Script):
    
    class Meta:
        name = "Build a new branch"
        description = "Example script showing how to auto-generate various objects for a new site."
        field_order = ['site_code', 'site_name', 'l2_count']
        commit_default = False

    site_code = StringVar(
        description="Enter the new site code"
    )
    site_name = StringVar(
        description="Enter the new site name"
    )
    l2_count = IntegerVar(
        description="How many L2 access switches at this site (0-9)?",
        label="L2 switches",
    )

    # use this to limit to a min/max range of numbers
    '''
    l2_count = ChoiceVar(
        required=True,
        choices=[(i, i) for i in range(10)],
        description=("How many L2 access switches at this site?"),
    )
    '''


    def run(self, data, commit):

        # define what device types will be installed at site
        # 
        # DeviceType.objects.get(model='CISCO2951/K9')
        router_model = DeviceType.objects.get(model='ISR4331')
        switch_model = DeviceType.objects.get(model='Catalyst 9300-48U')
        ats_model = DeviceType.objects.get(model='AP4450 ATS')
        ups_model = DeviceType.objects.get(model='Smart-UPS RT 2000VA RMLV2UNC')

        # assign device roles
        #
        # DeviceRole.objects.get(name='router')
        router_role = DeviceRole.objects.get(name='router')
        switch_role = DeviceRole.objects.get(name='switch')
        ats_role = DeviceRole.objects.get(name='power')
        ups_role = DeviceRole.objects.get(name='power')
        rack_role = RackRole.objects.get(name='Mix Use')

        # build a list/array to be used for switch naming convention
        L2_switch_letter = ['b', 'c', 'd', 'e', 'f', 'g','h', 'i', 'j']


        # Validate L2 switch count
        if data['l2_count'] not in range (0,10):
            self.log_failure('\nL2 switch count must be in range 0-9.')
            return()
        
        self.log_info(f"Number of L2 switches: {data['l2_count']}")

        # Create the new site from the user input data
        site_name = data['site_name']
        site_code = data['site_code']
        site = Site(
            name=site_name,
            slug=slugify(site_code),
            status=SiteStatusChoices.STATUS_PLANNED,
        )
        site.save()
        self.log_success(f"Created new site: {site}")


        # create the MDF rack group for the site
        rack_group_mdf = Location(
            name=f"MDF Room",
            slug=slugify(f"MDF Room"),
            site=site,
        )
        rack_group_mdf.save()
        self.log_success(f"Created rack group: {rack_group_mdf}")   

        # create the MDF rack 
        rack = Rack(
            name=f"A.1",
            site=site,
            role=rack_role,
            location=rack_group_mdf,
        )
        rack.save()
        self.log_success(f"Created rack: {rack}") 


        # Create the router
        device = Device(
            device_type=router_model,
            name=f'{site.slug}ra',
            site=site,
            status=DeviceStatusChoices.STATUS_PLANNED,
            device_role=router_role,
        )
        device.save()
        self.log_success(f"Created new device: {device}")

        # interface used to connect to L3 switch 
        nbiface = device.interfaces.get(name="GigabitEthernet0/0/1")
        self.log_info(f"Interface to L3 switch: {device} {nbiface}")

        # Create the L3 switch
        device = Device(
            device_type=switch_model,
            name=f'{site.slug}s01a',
            site=site,
            status=DeviceStatusChoices.STATUS_PLANNED,
            device_role=switch_role,
        )
        device.save()
        self.log_success(f"Created new device: {device}")

        # interface used to connect to router 
        z_nbiface = device.interfaces.get(name="GigabitEthernet1/0/48")
        self.log_info(f"Interface to router: {device} {z_nbiface}")


        # Create a cable between two interfaces
        cable = Cable(
                    termination_a=nbiface,
                    #termination_a_type=interface_ct,
                    termination_b=z_nbiface,
                    #termination_b_type=interface_ct,
                    #label=label,
                    status=LinkStatusChoices.STATUS_CONNECTED
        )
        cable.save()
        self.log_success(f"{nbiface.device} to {z_nbiface.device} : created cable {cable}")



        # Create the L2 switches
        for count in range(0, data['l2_count']):

            # create each switch
            device = Device(
                device_type=switch_model,
                name=f'{site.slug}s01{L2_switch_letter[count]}',
                site=site,
                status=DeviceStatusChoices.STATUS_PLANNED,
                device_role=switch_role,
            )
            device.save()
            self.log_success(f"Created new device: {device}")

            # create the IDF rack group for the site
            # self.log_info(f"Creating rack group: IDF-{L2_switch_letter[count].upper()}") 
            rack_group = Location(
                name=f'IDF-{L2_switch_letter[count].upper()}',
                slug=slugify(f'IDF-{L2_switch_letter[count].upper()}'),
                site=site,
            )
            rack_group.save()
            self.log_success(f"Created rack group: {rack_group}")   

            # create a rack 
            rack = Rack(
                name=f'Rack {L2_switch_letter[count].upper()}.1',
                site=site,
                role=rack_role,
                location=rack_group,
            )
            rack.save()
            self.log_success(f"Created rack: {rack}")   


        # Cable router to L3 switch


        # Optional: create some CSV output of the devices just created. 
        # This data could be used to import into another tool, for example.
        #
        # Header used for generating a CSV table output of all the new devices
        output = ['name,make,model']
        for device in Device.objects.filter(site=site):
            attrs = [
                device.name,
                device.device_type.manufacturer.name,
                device.device_type.model
            ]
            output.append(','.join(attrs))

        # Output the CSV Table results
        return('\n'.join(output))

 
