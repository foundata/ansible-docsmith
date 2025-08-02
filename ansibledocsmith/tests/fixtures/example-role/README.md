# example-role

TODO: Add role description here.

<!-- BEGIN ANSIBLE DOCSMITH -->
## Role Variables

The following variables can be configured for this role:

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `acmesh_domain` | str | ✅ | N/A | Primary domain name for the certificate |
| `acmesh_alt_names` | list | ❌ | `[]` | Alternative domain names (SAN) for the certificate. A Subject Alternative Name (SAN) in certificates allows multiple domain names or IP addresses to be associated with a single SSL/TLS certificate. SANs are commonly used for multi-domain certificates, ensuring all listed domains are securely protected with one public key. |
| `acmesh_email` | str | ✅ | N/A | Email address for ACME account registration |
| `acmesh_staging` | bool | ❌ | `false` | Use Let's Encrypt staging environment for testing |
| `acmesh_challenge_type` | str | ❌ | `"http-01"` | ACME challenge type to use for domain validation |

### Variable Details

#### acmesh_domain

Primary domain name for the certificate

- **Type**: `str`
- **Required**: Yes


#### acmesh_alt_names

Alternative domain names (SAN) for the certificate.

A Subject Alternative Name (SAN) in certificates allows multiple domain names or IP addresses to be associated with a single SSL/TLS certificate. SANs are commonly used for multi-domain certificates, ensuring all listed domains are securely protected with one public key.

- **Type**: `list`
- **Required**: No
- **Default**: `[]`
- **List Elements**: `str`


#### acmesh_email

Email address for ACME account registration

- **Type**: `str`
- **Required**: Yes


#### acmesh_staging

Use Let's Encrypt staging environment for testing

- **Type**: `bool`
- **Required**: No
- **Default**: `False`


#### acmesh_challenge_type

ACME challenge type to use for domain validation

- **Type**: `str`
- **Required**: No
- **Default**: `http-01`
- **Choices**: `http-01`, `dns-01`



## Example Playbook

```yaml
---
- hosts: servers
  become: yes
  vars:
    # acmesh_domain: # Primary domain name for the certificate
    acmesh_alt_names: []
    # acmesh_email: # Email address for ACME account registration
    acmesh_staging: False
    acmesh_challenge_type: http-01

  roles:
    - example-role
```

## Author Information

- foundata GmbH
- Andreas Haerter <ah@foundata.com>

<!-- END ANSIBLE DOCSMITH -->

## License

GPL-3.0-or-later

## Author Information

This role was created by [Your Name].
