from dcim.models import Device, Platform
from extras.scripts import *


class MyScript(Script):
    
    class Meta:
        name = "Excel 2-column Import"
        description = "Import cut and paste of two columns from Excel."
        field_order = ['field', 'text']
        commit_default = False

    CHOICES_field = (
        ('Device-serial', 'Device-serial'),
        ('Device-asset_tag', 'Device-asset_tag'),
        ('Device-platform', 'Device-platform'),
    )
    field = ChoiceVar(
        description="What model-field to update?",
        required=True,
        default='serial',
        choices=CHOICES_field,
    )

    text_in = TextVar(
        description=f"Paste in 2 columns of data from Excel (example: col1=device, col2=serial)",
        required=True,
    )

    def run(self, data, commit):

        #self.log_info(f"field={data['text_in']}")

        # parses out each line from the input text into a list
        lines = data['text_in'].split("\r\n")

        # this list holds the object being changed such as device
        object_list = []

        # this list holds the value such as a serial number
        value_list = []

        # loop through the lines of text
        for i in range(len(lines)):
            # for each line parse out the word delimited by tabs from excel
            words = lines[i].split("\t")
            object_list.append(words[0])
            value_list.append(words[1])

        self.log_info(f"object_list={object_list}")
        self.log_info(f"value_list={value_list}")

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
                    platform = Platform.objects.get(slug=value)
                    self.log_info(f"Updating {u_field} field in {name} to {value}")
                    my_object = Device.objects.get(name=name)
                    my_object.platform = platform
                    my_object.save()
                    self.log_success(f"Updated {u_field} field in {name} to {value}")

            else:
                self.log_info("Nothing to do")

        else:
            self.log_failure("Number of objects and values must match.")