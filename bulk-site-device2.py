from django.utils.text import slugify

from ipam.models import Prefix, IPAddress
from dcim.models import Cable, Device, DeviceRole, DeviceType, Manufacturer, Site, Location, Rack
from tenancy.models import Tenant

from dcim.choices import *
from ipam.choices import *

from extras.scripts import *

import netaddr


# common task functions which  can be reused in other scripts

def add_ip_to_interface(self, interface, newaddress):
    # create IP address as child of appropriate prefix
    newaddress = IPAddress(
        address = newaddress,
        status = IPAddressStatusChoices.STATUS_RESERVED,
        description = f"{interface.device} {interface.name}",
    )
    # save so the record can be assinged to the interface
    newaddress.save()
    # add ip address to interface
    interface.ip_addresses.add(newaddress)
    self.log_info(f"Saved address {newaddress} on {interface.device} {interface}")
    
    # this will remove ip addresses from an interface
    # interface.ip_addresses.remove(newaddress)
    return


def remove_ip_from_interface(self, interface, newaddress):
    # this will remove ip addresses from an interface
    interface.ip_addresses.remove(newaddress)
    self.log_info(f"Removed address {newaddress} from {interface.device} {interface}")
    return


def add_ip_prefix(self, interface, newprefix):
    # create new prefix as child of appropriate prefix
    newprefix = Prefix(
        prefix = newprefix,
        is_pool = False,
        status = PrefixStatusChoices.STATUS_RESERVED,
        description = f"{interface.device} {interface.name}",
    )
    # save so the record can be assinged to the interface
    result = newprefix.save()
    self.log_info(f"Saved prefix {newprefix} : {result}")
    return



class MyCustScript(Script):

    class Meta:
        name = "Bulk generate sites & devices"
        description = "Complex sample script for creating sites, devices, interfaces, \
                       cables, prefixes and address assignments to the interfaces. \
                       This will take a very long time to run if you make too many sites \
                       or devices, so be careful!!"
        field_order = ['site_prefix', 'site_count', 'device_role', 'device_model', 'device_count']
        commit_default = False

    site_prefix = StringVar(
        description = "Enter a site name prefix"
    )
    site_count = IntegerVar(
        description = "How many sites do you want to create"
    )
    manufacturer = ObjectVar(
        model = Manufacturer,
        required = False
    )
    device_model = ObjectVar(
        default = DeviceType.objects.get(model='C9200-48P'),
        description ="device model",
        model=DeviceType,
        #display_field = 'model',
        query_params = {
            'manufacturer_id': '$manufacturer'
        }
    )
    device_role = ObjectVar(
        default = DeviceRole.objects.get(name='Access Switch'),
        description = "Device role",
        model = DeviceRole,
        #display_field = 'name',
    )
    device_count = IntegerVar(
        description = "How many devices at each site"
    )


    def run(self, data, commit):


        TENANT_NAME = 'Sys Pro'

        # Setting mask to a /24-30 should work.  /31 is not supported with netaddr module.
        MASK = '/31'
        MASK_INT = 31
        SIZING_NET = '0.0.0.0' + MASK
        list_of_subnets = []

        # Header used for generating a CSV table output of all the new devices
        output = ['name,make,model']

        # add up home many IPs are needed based on MASK variable
        addys_required = data['site_count'] * (data['device_count'] - 2) * 2 * len(netaddr.IPNetwork(SIZING_NET))   


        # check for available IP addresses based on role name and tenant
        try:
            prefix = Prefix.objects.get(role__name='SP Monitor', tenant__name=TENANT_NAME)
        except:
            self.log_failure("Can't find any prefixes or some other error!")
        
        # available_ips = iter(prefix.get_available_ips())

        avail_cidrs = prefix.get_available_prefixes()
        self.log_info(f"Available cidrs {avail_cidrs}.")

        for new_cidr in avail_cidrs.iter_cidrs():
            self.log_info(f"Looping {new_cidr} len={len(netaddr.IPNetwork(new_cidr))} need={addys_required}.")
            if addys_required <= len(netaddr.IPNetwork(new_cidr)):
                self.log_info(f"Adequate address space exists in this cidr {new_cidr}.")
                break
            else:
                self.log_warning("This prefix too little, looking for another one.")
        
        
        # build a list of Subnets 
        
        # need to get subnets to assign to interfaces, so iterate through the available prefix and build a list of /30s
        # this creates a list of subnets of type IPNetwork('2.11.128.0/30')
        # Note: there is a limitation of netaddr as it cannot suport /31s

        for subnet in new_cidr.subnet(MASK_INT):
            list_of_subnets.append(subnet)
     
        self.log_info(f"{MASK} Subnets: {list_of_subnets}")


        # Use this varible to index list_of_subnets[subnet_index]
        subnet_index = 0

        # Create the new sites
        for site_num in range(1, data['site_count'] + 1):
            site_name = f"{data['site_prefix']}.{str(site_num)}"
            site = Site(
                name = site_name,
                tenant = Tenant.objects.get(name=TENANT_NAME),
                slug = slugify(site_name),
                status = SiteStatusChoices.STATUS_PLANNED,
            )
            site.save()
            self.log_success(f"Created new site: {site}")



            # Create devices in new site
            for device_num in range(1, data['device_count'] + 1): # the range starts with "1"
                device = Device(
                    site=site,
                    tenant = Tenant.objects.get(name=TENANT_NAME),
                    device_type=data['device_model'],
                    name = f"{data['device_model'].slug}.{device_num}",
                    status=DeviceStatusChoices.STATUS_PLANNED,
                    device_role=data['device_role'],
                )
                device.save()
                self.log_success(f"Created {device} @ {site}")

                # Somewhat lazy method, but assume the first two devices are core A/B switches
                # grab the first device and save as object for later
                if device_num == 1:
                    corea = device
                    corea_iface = device.interfaces.all() # also grab a list/array of all Core A's interfaces
                    #self.log_info(f"This is Core A: {device}")
                    self.log_info(f"This is Core As first interface: {corea_iface[0]}")

                # grab the second device and save as object for later
                if device_num == 2:
                    coreb = device
                    coreb_iface = device.interfaces.all() # also grab all Core B's interfaces
                    #self.log_info(f"This is Core B: {device}")
                    self.log_info(f"This is Core Bs first interface: {coreb_iface[0]}")

            # Use this varible to index ports on CORE A/B switches
            # start with 10th interface
            core_iface_index = 11

            # Iterate over each device in site, to do various things
            for device in Device.objects.filter(site=site):

                # A crude method to connect each device to core A and B
                # grab the core interfaces, no check is done to ensure enough ports
                a_iface = corea_iface[core_iface_index] # next interface on core A
                b_iface = coreb_iface[core_iface_index] # next interface on core B
              
                # don't connect anything between core A and B devices
                if device != corea and device != coreb:

                    self.log_info(f"Subnet Index = {subnet_index}")

                    '''
                    Topology of the interface naming - http://asciiflow.com/

                            +-------+
                            |       |
                            | SW-A  | A          AZ +------+
                            |       +---------------+      |
                            +-------+               |      |
                                                    | SW-n |
                            +-------+ B          BZ |      |
                            |       +---------------+      |
                            | SW-B  |               +------+
                            |       |
                            +-------+

                    future consideration: http://go.drawthe.net/

                    '''
 

                    az_iface = device.interfaces.get(name='GigabitEthernet1/0/1') # first interface goes to core A
                    bz_iface = device.interfaces.get(name='GigabitEthernet1/0/2') # second interface goes to core B

                    # first subnet used for link to A core, second one is for link to B core
                    a_az_subnet = list_of_subnets[subnet_index]
                    b_bz_subnet = list_of_subnets[subnet_index+1]
                    
                    add_ip_prefix(self, a_iface, str(a_az_subnet))
                    add_ip_prefix(self, b_iface, str(b_bz_subnet))

                    # add ip address to interface on core A ("A" side)
                    a_iface_address = str(list(a_az_subnet.iter_hosts())[0]) + MASK
                    self.log_info(f"{a_iface.device} {a_iface.name} assigned {a_iface_address} ")
                    add_ip_to_interface(self, a_iface, a_iface_address)
                    # add ip address to interface on other device ("Z" side)                    
                    az_iface_address = str(list(a_az_subnet.iter_hosts())[0] + 1) + MASK
                    add_ip_to_interface(self, az_iface, az_iface_address)
                    
                    

                    # add ip address to interface on core B ("A" side)
                    b_iface_address = str(list(b_bz_subnet.iter_hosts())[0]) + MASK
                    self.log_info(f"{b_iface.device} {b_iface.name} assigned {b_iface_address} ")
                    add_ip_to_interface(self, b_iface, b_iface_address)
                    # add ip address to interface on other device ("Z" side)                    
                    bz_iface_address = str(list(b_bz_subnet.iter_hosts())[0] + 1) + MASK
                    add_ip_to_interface(self, bz_iface, bz_iface_address)
                    

                    # Create a cable from core A to next device az_iface
                    cable = Cable(
                                termination_a=a_iface,
                                #termination_a_type=interface_ct,
                                termination_b=az_iface,
                                #termination_b_type=interface_ct,
                                #label=label,
                                status=LinkStatusChoices.STATUS_PLANNED
                    )
                    #self.log_info(f"{a_iface.device} {a_iface.name} to {z1_iface.device} {z1_iface.name} : saving cable")
                    cable.save()
                    self.log_success(f"{a_iface.device} to {az_iface.device} : created cable {cable}")

                    # Create a cable from core B to next device bz_iface
                    cable = Cable(
                                termination_a=b_iface,
                                #termination_a_type=interface_ct,
                                termination_b=bz_iface,
                                #termination_b_type=interface_ct,
                                #label=label,
                                status=LinkStatusChoices.STATUS_PLANNED
                    )
                    #self.log_info(f"{b_iface.device} {a_iface.name} to {z2_iface.device} {z1_iface.name} : saving cable")
                    cable.save()
                    self.log_success(f"{b_iface.device} to {bz_iface.device} : created cable {cable}")

                    # increment counters
                    core_iface_index = core_iface_index + 1
                    subnet_index = subnet_index + 2   # increment by 2, since two interfaces were allocated per loop
                    

                # build device attributes list for doing CSV output later
                attrs = [
                    device.name,
                    device.device_type.manufacturer.name,
                    device.device_type.model
                ]
                output.append(','.join(attrs))

        # Output the CSV Table results
        return('\n'.join(output)) 
