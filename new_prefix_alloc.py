from django.utils.text import slugify
from django.db import transaction

from ipam.models import Prefix, IPAddress, Role, VLAN
from dcim.models import Site
from tenancy.models import Tenant

from dcim.choices import *
from ipam.choices import *
from extras.scripts import *

import netaddr


CIDR_RangeStart = 30
CIDR_RangeEnd = 22


def add_ip_prefix(self, prefix, tenant, role, vlan):
    # create new prefix as child of appropriate prefix
    new_prefix = Prefix(
        prefix = prefix,
        is_pool = False,
        status = PrefixStatusChoices.STATUS_RESERVED,
        role = role,
        vlan = vlan,
        tenant = tenant,
        description = f"created using script",
    )
    # save so the record can be assinged to the interface
    try:
        with transaction.atomic():
            new_prefix.full_clean()
            new_prefix.save()
    except Exception as e:
        self.log_failure(f'Unable to create {prefix}:{e}')

    return





class MyCustScript(Script):

    class Meta:
        name = "Allocate Prefixes to VLAN"
        description = "calculates and generates child prefixes space from a parent prefix"
        field_order = ['tenant','role','vlan','site_count','ip_count','ip_reserved','parent_prefix']
        commit_default = False

    tenant = ObjectVar(
        description ="Tenant",
        model=Tenant,
    )
    role = ObjectVar(
        description = "Which role is this for?",
        model=Role,
    )
    vlan = ObjectVar(
        description = "Which vlan?",
        model=VLAN,
        query_params = {
            'role_id': '$role',
            'tenant_id': '$tenant',
        }
    )


    site_count = IntegerVar(
        description = "Max # of sites"
    )
    ip_count = IntegerVar(
        description = "Max # of IP addresses per site for this role",
        label="VLAN IP Count"
    )
    ip_reserved = IntegerVar(
        description = "# of IP addresses reserved for the net infra, such as the router/gateway IP",
        default = 3,
        label="How many extra IPs to reserve for infrastrucure?"
    )

    parent_prefix = ObjectVar(
        description ="Choose parent prefix",
        model=Prefix,
        query_params = {
            'tenant_id': '$tenant',
            'role_id': '$role'
        }
    )



    def run(self, data, commit):


        # Setting mask to a /24-30 should work.  /31 is not supported with netaddr module.
        list_of_subnets = []
        PARENT_PREFIX = data['parent_prefix']
        SITES = data['site_count']
        TENANT = data['tenant']
        VLAN = data['vlan']
        ROLE = data['role']
                
        subtotal_ip_count = data['ip_count'] + data['ip_reserved']

        if subtotal_ip_count > 1024:
            self.log_failure("IP Count must be less than 1024")
            return

        # figure out the required per site subnet/vlan mask        
        for mask in range(CIDR_RangeStart, CIDR_RangeEnd, -1):
            network_string = '0.0.0.0/' + str(mask)
            network_len = len(netaddr.IPNetwork(network_string))
            #self.log_debug(f"mask={mask}  len={network_len}")
            if subtotal_ip_count < network_len:
                self.log_success(f"For {subtotal_ip_count} IPs the required mask is /{mask}")
                break  # no need to loop anymore, as mask size was found
 
        # add up how many IPs are needed based on network length calulated above
        addys_required = SITES * network_len
        
        self.log_info(f"Total address space required = {addys_required}")
        self.log_info(f"Parent prefix to be used = {PARENT_PREFIX}")

        # grab the parent prefix and assign to the working prefix varible "prefix"
        try:
            prefix = PARENT_PREFIX
        except:
            self.log_failure("Can't find any prefixes or some other error!")
            return
        
        # available_ips = iter(prefix.get_available_ips())

        avail_cidrs = prefix.get_available_prefixes()
        self.log_info(f"Available cidrs {avail_cidrs}.")

        for new_cidr in avail_cidrs.iter_cidrs():
            #self.log_info(f"Looping {new_cidr} len={len(netaddr.IPNetwork(new_cidr))} need={addys_required}.")
            if addys_required <= len(netaddr.IPNetwork(new_cidr)):
                self.log_info(f"Adequate address space exists in this cidr {new_cidr}.")
                found_cidr = True
                break
            else:
                pass
                #self.log_warning("This prefix too little, looking for another one.")
        
        if found_cidr:
            # build a list of Subnets 
            
            # need to get subnets to assign to interfaces, so iterate through the
            # available prefix and build a list of /n defined by MASK variable)
            # this creates a list of subnets of type IPNetwork('2.11.128.0/n')
            # Note: there is a limitation of netaddr as it cannot suport /31s

            site_count = SITES
            for subnet in new_cidr.subnet(int(mask)):
                list_of_subnets.append(subnet)
                self.log_debug(f"Adding {subnet} {TENANT} {ROLE} {VLAN}")
                site_count = site_count - 1
                if site_count > 0:
                    add_ip_prefix(self, subnet, TENANT, ROLE, VLAN)
                else:
                    break

            #self.log_debug(f"{mask} Subnets: {list_of_subnets}")

        else:
            self.log_failure("Could not find any suitable prefix for this requirement,\
                Please contact the network team (mnsdata@oncor.com).")

        return
