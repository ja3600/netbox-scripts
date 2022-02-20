from django.utils.text import slugify

from dcim.models import Site
from extras.scripts import *

class MyScript(Script):

    class Meta:
        name = "Update site ASNs"
        description = "Takes python dict input and updates the site's ASN"
        commit_default = False

    asn = StringVar(
        description = "Enter dict string (use all uppercase site/facility code)",
        default = {'AAAA': 64600, 'BBBB': 64601, 'CCCC': 64603},
    )


    def run(self, data, commit):

        asn = data['asn']
                
        for site in Site.objects.all():
            try:        
                # this does a dict lookup or returns error if site not found
                site.asn = asn[site.facility]
                site.save()
            except KeyError:
                self.log_warning(f"site code {site.facility} not found or missing")
        return