#!/usr/bin/python

'''
    NetBox import objects and their relationships using a YAML document

    source repo: https://github.com/ja3600/yaml-to-netbox.git

    Much credit goes to these great resources: 
    https://pyyaml.org/wiki/PyYAMLDocumentation
    https://matthewpburruss.com/post/yaml/
    https://www.cloudbees.com/blog/yaml-tutorial-everything-you-need-get-started
    https://www.json2yaml.com/convert-yaml-to-json

    And of course thanks to everyone that made NetBox possible

'''

from django.utils.text import slugify
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
import yaml, io, sys, re

from dcim.choices import DeviceStatusChoices, SiteStatusChoices, LinkStatusChoices
from dcim.models import Site, Location, Rack, RackRole
from dcim.models import Device, DeviceRole, DeviceType, Interface, Cable
from circuits.models import Circuit, CircuitType, CircuitTermination, ProviderNetwork, Provider
from tenancy.models import Tenant
from extras.models import Tag
from extras.scripts import Script, ChoiceVar, ObjectVar, StringVar, IntegerVar, MultiObjectVar, FileVar, TextVar
#from extras.scripts import *

from netbox.settings import VERSION
from utilities.choices import ColorChoices
from utilities.forms.constants import ALPHANUMERIC_EXPANSION_PATTERN
from utilities.forms.utils import expand_alphanumeric_pattern


#usually this would point to the netbox scripts directory
YAML_PATH = "/opt/netbox/netbox/scripts/"
DEFAULT_YAML_FILE = "example_1.yaml"

# the YAML document schema tested and working with the above script version
SUPPORTED_SCHEMA_VERSIONS = [1]


NO_CHOICE = ()
# https://github.com/netbox-community/netbox/issues/8228
# Only apply to Netbox < v3.1.5
if [int(n) for n in VERSION.split('-')[0].split('.')] < [3, 1, 5]:
    NO_CHOICE = (
        ('', '---------'),
    )

TERM_CHOICES = (
    ('interfaces', 'Interfaces'),
    ('frontports', 'Front Ports'),
    ('rearports', 'Rear Ports'),
)

def expand_pattern(value):
    # Example: ge-0/0/[5,7,12-23]
    if not value:
        return ['']
    if re.search(ALPHANUMERIC_EXPANSION_PATTERN, value):
        return list(expand_alphanumeric_pattern(value))
    return [value]




class SiteBuilder(Script):

    class Meta:
        name = "YAML to NetBox"
        description = "import objects and their relationships using YAML documents"

    yamlfile = FileVar(
        description="choose the yaml file",
        required=False,
    )

    yamltext = TextVar(
        description="edit or paste in YAML text",
        default=open(YAML_PATH+DEFAULT_YAML_FILE, "r").read()
    )



    def run(self, data, commit):

        def remove_empty_from_dict(d):
            '''
            used to scrub the attributes passed to create objects
            in this case any empty value are removed from the dict
            '''
            if type(d) is dict:
                return dict((k, remove_empty_from_dict(v)) for k, v in d.items() if v and remove_empty_from_dict(v))
            elif type(d) is list:
                return [remove_empty_from_dict(v) for v in d if v and remove_empty_from_dict(v)]
            else:
                return d


        def create_site(data):
            '''
            custom logic for creating new sites
            '''
            
            #do a quick slug validation
            if data['slug'] == None:
                slug=slugify(data['name'])
            else:
                slug=slugify(data['slug'])

            attributes = {
                'name':data['name'],
                'slug':slug,
                'facility':data['facility'],
                'status':data['status'],
                'physical_address': data['physical_address'],
                'tenant':TENANT,
            }
            kargs = remove_empty_from_dict(attributes)

            site = Site(**kargs)

            site.save()
            self.log_success(f"Created new site: {site}")
            return site


        def create_rack(data, site):
            '''
            custom logic for creating new racks
            '''

            attributes = {
                'name':data['name'],
                'status':data['status'],
                'type':data['type'],
                'width':data['width'],
                'u_height':data['u_height'],
                'site':site,
                'role':RackRole.objects.get(name=data['role']),
                'tenant' : TENANT,
            }
            kargs = remove_empty_from_dict(attributes)

            rack = Rack(**kargs)
            try:
                with transaction.atomic():
                    rack.full_clean()
                    rack.save()
            except Exception as e:
                self.log_failure(f'Unable to create {rack}:{e}')

            self.log_success(f"Created rack: {rack}")
            return rack


        def create_location(data, site):
            '''
            FUTURE USE: Not implemented fully yet
            custom logic for creating new locations
            '''

            attributes = {
                'name':data['name'],
                'slug':slugify(data['name']),
                'site':site,
                'role':RackRole.objects.get(name=data['role']),
                'tenant':TENANT,
            }
            kargs = remove_empty_from_dict(attributes)

            location = Location(**kargs)

            location.save()
            self.log_success(f"Created location: {location} in {site}")
            return location


        def create_device(data):
            '''
            custom logic for creating new devices
            '''

            site = Site.objects.get(facility=data['facility'])

            attributes = {
                'name':data['name'],
                'site':site,
                'device_type':DeviceType.objects.get(model=data['device_type']),
                'status':data['status'],
                'device_role':DeviceRole.objects.get(name=data['device_role']),
                'rack':Rack.objects.get(site=site, name=data['rack']),
                'position':data['position'],
                'face':data['face'],
                'tenant':TENANT,
            }
            kargs = remove_empty_from_dict(attributes)

            device = Device(**kargs)

            device.save()
            self.log_success(f"Created new device: {device} in {data['rack']}")
            return device


        def create_interface(data, device):
            '''
            custom logic for creating new interfaces
            '''

            # lookup the LAG id, if the 'lag' key is not empty
            if data['lag'] != None :
                lag = Interface.objects.get(device=device, name=data['lag'])
                self.log_info(f"LAG was found: {lag}")
            else:
                lag = None

            attributes = {
                'name':data['name'],
                'device':device,
                'type':data['type'],
                'lag':lag,
                'description':f"{device} {data['name']}",
            }
            kargs = remove_empty_from_dict(attributes)

            interface = Interface(**kargs)

            interface.save()
            self.log_success(f"-- created new interface: {interface} for {device}")
            return interface


        def create_circuit(data):
            '''
            custom logic for creating new circuits
            '''

            #build the circuit object
            circuit = Circuit(
                cid=data['cid'],
                provider=Provider.objects.get(name=data['provider']),
                type=CircuitType.objects.get(name=data['type']),
                status=data['status'],
                commit_rate=data['commit_rate'],
                tenant=TENANT,
            )
            circuit.save()

            #get the A side for circuit termination, this must be a site
            a_facility = Site.objects.get(facility=data['a_facility'])

            #build the A-side circuit termination
            a_cterm = CircuitTermination(
                circuit=Circuit.objects.get(cid=data['cid']),
                term_side='A',
                site=a_facility,
                #provider_network='',
                port_speed=data['port_speed'],
                description=''
            )
            a_cterm.save()

            #get the Z side for circuit termination, this can be a site or provider network
            if data['z_facility'] != None :
                z_facility = Site.objects.get(facility=data['z_facility'])

                # build the Z-side circuit termination (this is a point-to-point)
                z_cterm = CircuitTermination(
                    circuit=Circuit.objects.get(cid=data['cid']),
                    term_side='Z',
                    site=z_facility,
                    port_speed=data['port_speed'],
                    description=''
                )
                z_cterm.save()                
            
            if data['z_provider_net'] != None :
                z_provider_net = ProviderNetwork.objects.get(name=data['z_provider_net'])

                #build the A-side circuit termination (this is a multi-point)
                z_cterm = CircuitTermination(
                    circuit=Circuit.objects.get(cid=data['cid']),
                    term_side='Z',
                    provider_network=z_provider_net,
                    port_speed=data['port_speed'],
                    description=''
                    
                )
                z_cterm.save()

            self.log_success(f"Created circuit {circuit}")
            return 


        def create_cable(data):
            '''
            custom logic for creating new cables
            '''

            #no circuit ID specified, so use direct <DeviceA>--<DeviceB> connection
            if data['circuit_id'] == None:
                #setup the A side
                termination_a_type = ContentType.objects.get(app_label='dcim', model='interface')
                #get the device and interface
                device_a = Device.objects.get(name=data['termination_a_device'])
                interface_a = Interface.objects.get(device=device_a, name=data['termination_a_interface'])
                label=f"{device_a} {interface_a}"
                
                #setup the B side
                termination_b_type = ContentType.objects.get(app_label='dcim', model='interface')
                #get the device and interface
                device_b = Device.objects.get(name=data['termination_b_device'])
                interface_b = Interface.objects.get(device=device_b, name=data['termination_b_interface'])
                label+=f" to {device_b} {interface_b}"

                #build the <DeviceA>--<DeviceB> cable object
                cable = Cable(
                    termination_a_type=termination_a_type,
                    termination_a=interface_a,
                    termination_b_type=termination_b_type,
                    termination_b=interface_b,
                    type=data['type'],
                    length=data['length'],
                    label=label,
                    #status=LinkStatusChoices.STATUS_PLANNED,
                    status=data['status'],
                    tenant=TENANT,
                )
                cable.save()
                self.log_success(f"Created cable: {cable}")
                return



            #use <DeviceA>--(circuitA-circuitZ)--<DeviceB> logic
            elif data['termination_b_device'] != None:  
                #setup the A side                
                termination_a_type = ContentType.objects.get(app_label='dcim', model='interface')
                #get the device and interface
                device_a = Device.objects.get(name=data['termination_a_device'])
                interface_a = Interface.objects.get(device=device_a, name=data['termination_a_interface'])
                label = f"{device_a} {interface_a}"
                
                #setup the B side (A side of circuit)
                termination_b_type = ContentType.objects.get(app_label='circuits', model='circuittermination')
                #derive termination from the circuit ID and A-side
                circuit_id = Circuit.objects.get(cid=data['circuit_id'])
                interface_b = CircuitTermination.objects.get(circuit=circuit_id, term_side='A')
                label += f" to {interface_b} CKTID={circuit_id}"

                #build the <DeviceA>--(circuitA..... cable object
                cable = Cable(
                    termination_a_type=termination_a_type,
                    termination_a=interface_a,
                    termination_b_type=termination_b_type,
                    termination_b=interface_b,
                    type=data['type'],
                    length=data['length'],
                    label=label,
                    status=LinkStatusChoices.STATUS_PLANNED
                )
                cable.save()
                self.log_success(f"Created cable: {cable}")

                #setup the B side                
                termination_a_type = ContentType.objects.get(app_label='dcim', model='interface')
                #get the device and interface
                device_a = Device.objects.get(name=data['termination_b_device'])
                interface_a = Interface.objects.get(device=device_a, name=data['termination_b_interface'])
                label = f"{device_a} {interface_a}"
                
                #setup the B side (Z side of circuit)
                termination_b_type = ContentType.objects.get(app_label='circuits', model='circuittermination')
                #derive termination from the circuit ID and A-side
                circuit_id = Circuit.objects.get(cid=data['circuit_id'])
                interface_b = CircuitTermination.objects.get(circuit=circuit_id, term_side='Z')
                label += f" to {interface_b} CKTID={circuit_id}"

                #build the <DeviceB>--(circuitZ..... cable object
                cable = Cable(
                    termination_a_type=termination_a_type,
                    termination_a=interface_a,
                    termination_b_type=termination_b_type,
                    termination_b=interface_b,
                    type=data['type'],
                    length=data['length'],
                    label=label,
                    status=LinkStatusChoices.STATUS_PLANNED
                )
                cable.save()
                self.log_success(f"Created cable: {cable}")

            #assumes <DeviceA>--(circuitA-circuitZ)--<ProviderNetwork> logic
            else:  
                #setup the A side                
                termination_a_type = ContentType.objects.get(app_label='dcim', model='interface')
                #get the device and interface
                device_a = Device.objects.get(name=data['termination_a_device'])
                interface_a = Interface.objects.get(device=device_a, name=data['termination_a_interface'])
                label = f"{device_a} {interface_a}"
                
                #setup the B side (A side of circuit)
                termination_b_type = ContentType.objects.get(app_label='circuits', model='circuittermination')
                #derive termination from the circuit ID and A-side
                circuit_id = Circuit.objects.get(cid=data['circuit_id'])
                interface_b = CircuitTermination.objects.get(circuit=circuit_id, term_side='A')
                label += f" to {interface_b} CKTID={circuit_id}"
                if DEBUG: self.log_debug(f"Building cable: {label}")

                #build the <DeviceA>--(circuitA..... cable object
                cable = Cable(
                    termination_a_type=termination_a_type,
                    termination_a=interface_a,
                    termination_b_type=termination_b_type,
                    termination_b=interface_b,
                    type=data['type'],
                    length=data['length'],
                    label=label,
                    status=LinkStatusChoices.STATUS_PLANNED
                )
                cable.save()
                self.log_success(f"Created cable: {cable}")



        #the purpose of all of these sb_ functions is to iterate through the object lists

        def sb_sites(sites):
            '''
            part of SiteBuilder to create any site, if any exist in the YAML document            
            '''

            print('\nProcessing Sites...')
            for site in sites:
                #print(site.items())
                #print(site['name'])
                new_site = create_site(site)
                if "racks" in site:
                    for rack in site['racks']:
                        #print(rack.items())
                        #print('...', rack['name'])
                        create_rack(rack, new_site)
                else:
                    self.log_info(f"{new_site} has no racks")
            return

        def sb_devices(devices):
            '''
            part of SiteBuilder to create any devices, if any exist in the YAML document            
            '''

            print('\nProcessing Devices...')
            for device in devices:
                #print(device.items())
                #print(device['name'])
                new_device = create_device(device)
                if "interfaces" in device:
                    for interface in device['interfaces']:
                        #print(interface.items())
                        print('...', interface['name'])
                        create_interface(interface, new_device)
                else:
                    print('(no interfaces)')
            return

        def sb_circuits(circuits):
            '''
            part of SiteBuilder to create any circuits, if any exist in the YAML document            
            '''

            print('\nProcessing circuits...')
            for circuit in circuits:
                #print(circuit.items())
                #print(circuit['name'])
                create_circuit(circuit)
            return

        def sb_cables(cables):
            '''
            part of SiteBuilder to create any cables, if any exist in the YAML document            
            '''

            print('\nProcessing Cables...')
            for cable in cables:
                #print(cable.items())
                #print(cable['name'])
                create_cable(cable)
            return


        def WipeSite(sites):
            '''
            WARNING: This deletes the sites specified in the YAML document.
            Use only during script dev/testing to avoid duplication errors.
            '''
            # alternate means to lookup up sites
            # sites = Site.objects.filter(name__contains=name_contains).all()
            
            self.log_warning(f"{len(sites)} sites will be wiped/erased, if they already exist")
            
            for site in sites:
                
                #query for the site name
                s = Site.objects.filter(name=site['name'])

                if s.count() == 1:
                    #if site exists, the expectation is exactly one site is found
                    # thus, reference first item in list returned from the site query above
                    siteid = s.first()
                    self.log_debug(f"found existing {siteid} and it will be deleted")
                else:
                    self.log_debug(f"No sites to delete, skipping this")
                    return

                for device in Device.objects.filter(site=siteid):
                    self.log_debug(f"Deleted {device.delete()}")
                
                for racks in Rack.objects.filter(site=siteid):
                    self.log_debug(f"Deleted {racks.delete()}")

                for racks in Rack.objects.filter(site=siteid):
                    self.log_debug(f"Deleted {racks.delete()}")

                ct = CircuitTermination.objects.filter(site=siteid, term_side='A').all()
                for ct_item in ct:
                    circuit_to_delete = Circuit.objects.get(cid=ct_item.circuit)
                    self.log_debug(f"Deleted {circuit_to_delete.delete()}")

                self.log_warning(f"{siteid.delete()} was deleted!")

            return


        def SiteBuilder(yaml_doc):
            '''
            loads and parses through YAML data first level keys
            '''

            result =  yaml.safe_load(yaml_doc)

            # The yaml document is loaded as one big nested python dictonary
            #  the first level keys are referenced as result['key'] 
            
            # these are some variables that might be useful in the future
            yaml_vars = result['vars']

            # version support pre-checks
            schema = yaml_vars['schema_verison']
            if schema in SUPPORTED_SCHEMA_VERSIONS:
                self.log_success(f"Passed version check: script supports {SUPPORTED_SCHEMA_VERSIONS} and yaml schema is ver {schema}")
            else:
                self.log_failure(f"Sorry, yaml schema verison {schema} not supported")

            #deal with the *debug* key
            global DEBUG #make this global
            try:
                #look for the key in YAML doc, if not present assume false
                DEBUG = yaml_vars['debug']
                self.log_debug(f"Debug mode = {DEBUG}")
            except:
                DEBUG = False

            if DEBUG:
                self.log_debug(f" !! DEBUG MODE IS ENABLED !!")
                self.log_debug(f"yaml_vars: {yaml_vars}")
                # for dev/testing during debugging

            #deal with the *tenant* key
            global TENANT #make this global
            try:                
                TENANT = Tenant.objects.get(name=yaml_vars['globals']['tenant'])                
                self.log_info(f"Certain objects will be created under tenant: {TENANT}")
            except:
                self.log_info(f"No Tenant was specified")
                TENANT = None

            #deal with the *wipe* key
            try:
                #look for the key in YAML doc, if not present assume false
                WIPE = yaml_vars['wipe']
                self.log_warning(f"Wipe status = {WIPE}")
            except:
                WIPE = False

            if WIPE:
                # for dev/testing during debugging
                WipeSite(result['sites'])



            # using if statements to only process the keys that exist in the YAML document
            if "sites" in result:
                sb_sites(result['sites'])

            if "devices" in result:
                sb_devices(result['devices'])

            if "circuits" in result:
                sb_circuits(result['circuits'])

            # note: cables should be processed last    
            if "cables" in result:
                sb_cables(result['cables'])

            return


        ##
        # Main Execution Begins Here..
        ##

        # import a file
        if data['yamlfile']:
            with data['yamlfile'] as stream:
                try:
                    SiteBuilder(stream)
                except yaml.YAMLError as exc:
                    self.log_failure(exc)
        
        # use the default sample YAML file
        else:
            with io.StringIO(data['yamltext']) as stream:
                try:
                    SiteBuilder(stream)
                except yaml.YAMLError as exc:
                    self.log_failure(exc)

        self.log_success(f"YAML processing completed")

        return 