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
| `acmesh_webroot_path` | path | ❌ | `"/var/www/html"` | Path to webroot directory for HTTP-01 challenge |
| `acmesh_dns_provider` | str | ❌ | N/A | DNS provider for DNS-01 challenge |
| `acmesh_config` | dict | ❌ | `{}` | Additional configuration options |
| `acmesh_hooks` | dict | ❌ | `{}` | Custom hooks for certificate lifecycle events |

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


#### acmesh_webroot_path

Path to webroot directory for HTTP-01 challenge

- **Type**: `path`
- **Required**: No
- **Default**: `/var/www/html`


#### acmesh_dns_provider

DNS provider for DNS-01 challenge

- **Type**: `str`
- **Required**: No
- **Choices**: `cloudflare`, `route53`, `digitalocean`


#### acmesh_config

Additional configuration options

- **Type**: `dict`
- **Required**: No
- **Default**: `{}`

**Suboptions**:

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `force_renewal` | bool | ❌ | `false` | Force certificate renewal even if not expired |
| `key_size` | int | ❌ | `2048` | RSA key size in bits |

#### acmesh_hooks

Custom hooks for certificate lifecycle events

- **Type**: `dict`
- **Required**: No
- **Default**: `{}`

**Suboptions**:

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `pre_issue` | str | ❌ | N/A | Command to run before certificate issuance |
| `post_issue` | str | ❌ | N/A | Command to run after certificate issuance |
| `deploy` | str | ❌ | N/A | Command to run for certificate deployment |


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
    acmesh_webroot_path: /var/www/html
    # acmesh_dns_provider: # DNS provider for DNS-01 challenge
    acmesh_config: {}
    acmesh_hooks: {}

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
