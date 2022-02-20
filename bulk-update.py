from dcim.models import Device
from extras.scripts import *


class MyScript(Script):
    
    class Meta:
        name = "Bulk Update Fields"
        description = "Quick method to update one field of an object."
        field_order = ['object_model', 'list_of_objects', 'List_of_values', 'field']
        commit_default = False

    CHOICES_field = (
        ('Device-serial', 'Device-serial'),
        ('Device-asset_tag', 'Device-asset_tag'),
        ('Device-platform', 'Device-platform'),
        ('Site-ASN', 'Site-ASN'),

    )
    field = ChoiceVar(
        description="What model-field to update?",
        required=True,
        default='serial',
        choices=CHOICES_field,
    )

    list_of_objects = StringVar(
        description=f"What objects (comma delimited)?",
        required=True,
        default='R101, SW101'
    )

    list_of_values = StringVar(
        description="What values (comma delimited)?",
        required=True,
        default='AB123412324, DC56785678'
    )


    def run(self, data, commit):

        # self.log_info(f"field={data['field']}")
        # self.log_info(f"list_of_objects={data['list_of_objects']}")
        # self.log_info(f"list_of_values={data['list_of_values']}")

        object_list = data['list_of_objects'].split(",")
        value_list = data['list_of_values'].split(",")
 
        u_field = data['field']


        if len(object_list) == len(value_list):

            if u_field == 'Device-serial':
                for i in range(len(object_list)):
                    name = object_list[i].strip()
                    value = value_list[i].strip()
                    my_object = Device.objects.get(name=name)
                    my_object.serial = value
                    my_object.save()
                    self.log_success(f"Updated {u_field} field in {name} to {value}")

            elif u_field == 'Device-asset_tag':
                for i in range(len(object_list)):
                    name = object_list[i].strip()
                    value = value_list[i].strip()
                    my_object = Device.objects.get(name=name)
                    my_object.asset_tag = value
                    my_object.save()
                    self.log_success(f"Updated {u_field} field in {name} to {value}")

            elif u_field == 'Device-platform':
                for i in range(len(object_list)):
                    name = object_list[i].strip()
                    value = value_list[i].strip()
                    my_object = Device.objects.get(name=name)
                    my_object.platform = value
                    my_object.save()
                    self.log_success(f"Updated {u_field} field in {name} to {value}")

            # note this is limited to just adding one ASN at a time, ASN must already exist in NetBox
            elif u_field == 'Site-ASN':
                for i in range(len(object_list)):
                    name = object_list[i].strip()
                    value = value_list[i].strip()
                    asn = ASN.objects.get(asn=value)
                    my_object = Site.objects.get(name=name)
                    my_object.asns.set([asn.id])
                    my_object.save()
                    self.log_success(f"Updated {u_field} field in {name} to {value}")

            else:
                self.log_info("Nothing to do")

        else:
            self.log_failure("Number of objects and values must match.")


