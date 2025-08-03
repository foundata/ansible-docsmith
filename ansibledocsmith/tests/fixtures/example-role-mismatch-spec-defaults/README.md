# DocSmith for Ansible example-role README (for testing)

This role intentionally contains several flaws that should be detected during validation, resulting in errors. It is used to test the validation functionality, which ensures consistency between the `defaults/` files and the `argument_specs.yml` file. The validation checks include:

1. **ERROR:** Variables present in `defaults/` but missing from `argument_specs.yml`.
2. **ERROR:** Variables with `default:` values defined in `argument_specs.yml` but missing from the entry-point files in `defaults/`.
3. **WARNING:** Unknown keys in `argument_specs.yml`.
4. **NOTICE:** Potential mismatches, where variables are listed in `argument_specs.yml` but not in `defaults/`, for user awareness.

Warnings and notices are typically displayed only if no errors are found, as errors are treated as exceptions that stop further validation.


This README file is also a dummy file to show that existing content outside the `ANSIBLE DOCSMITH` markers will not be touched.

<!-- BEGIN ANSIBLE DOCSMITH -->
This line will be replaced as it is between the markers! Any content between them is maintained by `ansible-docsmith`.
<!-- END ANSIBLE DOCSMITH -->


## License

`GPL-3.0-or-later`.


## Author Information

This role was created for testing purposes.

Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet. Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet.