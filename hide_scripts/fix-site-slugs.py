from django.utils.text import slugify

from dcim.models import Site
from extras.scripts import *

class MyScript(Script):

    class Meta:
        name = "Fix Site Slug"
        description = "updates all sites to use the lower case facility code as the site slug"
        commit_default = False

    def run(self, data, commit):

        for site in Site.objects.all():
            try:        
                site.slug = site.facility.lower()
                site.save()
            except KeyError:
                self.log_warning(f"Could not update site [{site}]")