import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Task 5.2.1.4, part 3 of 3: apply the new constraints (IranProvince
    choices, postal code regex validator, shrunk max_length, IR
    country default) now that 0003's data cleanup has already run in
    its own prior transaction. Kept separate from that RunPython step
    for the Postgres-specific reason documented there ("pending
    trigger events").
    """

    dependencies = [
        ("dashboard", "0003_clear_invalid_province_and_postal_code_data"),
    ]

    operations = [
        migrations.AlterField(
            model_name="address",
            name="province",
            field=models.CharField(
                max_length=30,
                blank=True,
                choices=[
                    ("alborz", "Alborz"),
                    ("ardabil", "Ardabil"),
                    ("bushehr", "Bushehr"),
                    ("chaharmahal_and_bakhtiari", "Chaharmahal and Bakhtiari"),
                    ("east_azerbaijan", "East Azerbaijan"),
                    ("fars", "Fars"),
                    ("gilan", "Gilan"),
                    ("golestan", "Golestan"),
                    ("hamadan", "Hamadan"),
                    ("hormozgan", "Hormozgan"),
                    ("ilam", "Ilam"),
                    ("isfahan", "Isfahan"),
                    ("kerman", "Kerman"),
                    ("kermanshah", "Kermanshah"),
                    ("khuzestan", "Khuzestan"),
                    ("kohgiluyeh_and_boyer_ahmad", "Kohgiluyeh and Boyer-Ahmad"),
                    ("kurdistan", "Kurdistan"),
                    ("lorestan", "Lorestan"),
                    ("markazi", "Markazi"),
                    ("mazandaran", "Mazandaran"),
                    ("north_khorasan", "North Khorasan"),
                    ("qazvin", "Qazvin"),
                    ("qom", "Qom"),
                    ("khorasan_razavi", "Khorasan Razavi"),
                    ("semnan", "Semnan"),
                    ("sistan_and_baluchestan", "Sistan and Baluchestan"),
                    ("south_khorasan", "South Khorasan"),
                    ("tehran", "Tehran"),
                    ("west_azerbaijan", "West Azerbaijan"),
                    ("yazd", "Yazd"),
                    ("zanjan", "Zanjan"),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="address",
            name="postal_code",
            field=models.CharField(
                max_length=10,
                blank=True,
                validators=[
                    django.core.validators.RegexValidator(
                        regex="^\\d{10}$",
                        message="Enter a valid 10-digit Iranian postal code.",
                    )
                ],
            ),
        ),
        migrations.AlterField(
            model_name="address",
            name="country",
            field=models.CharField(default="IR", max_length=10),
        ),
    ]
