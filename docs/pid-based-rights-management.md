# PID-based rights management in AVefi

## Handle structure

### Data provider handle (e.g. for SDK)

In order to properly manage data ownership in the AVefi project, each
data provider is identified by a handle. For demonstration purposes,
consider the data provider Stiftung Deutsche Kinemathek (SDK). It
might be identified by the handle `21.11155/SDK` and the handle record
should look like this:

| index | type      | sample value (ePIC API v3)                                                                                                       | remarks                                                                                                                  |
|-------|-----------|----------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------|
| 1     | KIP       | ...                                                                                                                              |                                                                                                                          |
| 2     | has_agent | {"has_name": "SDK", "type": "CorporateBody", "same_as": [{"category": "avefi:ISILResource", "id": "DE-MUS-407010"}]}             |                                                                                                                          |
| 3     | URL       | https://testbed.av-efi.net/search/?has_issuer_name%5B0%5D=Deutsche%20Kinemathek%20-%20Museum%20f%C3%BCr%20Film%20und%20Fernsehen | URL to collection of provided data, could be something else, too                                                         |
| 4     | ou        | sdk                                                                                                                              | Academiccloud ID for organisation, so interactive logins via frontend can be granted privileges according to affiliation |
| 100   | HS_ADMIN  | {"adminId": "21.11155/USER1", "adminIdIndex": 300}                                                                               |                                                                                                                          |
| 200   | HS_VLIST  | [{"handle": "21.11155/SDK", "index": 300}]                                                                                       | May be extended in case multiple PubKeys should become desirable for some reason.                                        |
| 300   | HS_PUBKEY | ...                                                                                                                              | First PubKey associated with this handle.                                                                                |

### WorkVariant editors handle

Handle records describing a moving image work (AVefi category
WorkVariant) must be modifiable by all data providers. Hence, we need
a VLIST handle representing all data providers.

Handle record for `21.11155/work_variant_editors`:

| index | type     | sample value (ePIC API v3)                                                           | remarks                                 |
|-------|----------|--------------------------------------------------------------------------------------|-----------------------------------------|
| 100   | HS_ADMIN | {"adminId": "21.11155/USER1", "adminIdIndex": 300}                                   |                                         |
| 200   | HS_VLIST | [{"handle": "21.11155/SDK", "index": 200}, {"handle": "21.11155/HDF", "index": 200}] | List should include all data providers. |

### WorkVariant Handle

Handle record for something like `21.11155/sample_work`:

| index | type       | sample value (ePIC API v3)                                                          | remarks                                                               |
|-------|------------|-------------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| 1     | KIP        | http://typeapi.lab.pidconsortium.net/v1/types/schema/21.T11969/873d5c9f6ebbffecf1df | AVefi schema                                                          |
| 2     | has_record | {"category": "avefi:WorkVariant", ...}                                              | Moving image work record according to AVefi schema.                   |
| 3     | URL        | https://www.av-efi.net/res/21.11155/sample_work                                     |                                                                       |
| 100   | HS_ADMIN   | {"adminId": "21.11155/USER1", "adminIdIndex": 300}                                  |                                                                       |
| 101   | HS_ADMIN   | {"adminId": "21.11155/work_variant_editors", "adminIdIndex": 200}                   | WorkVariant records are meant to be modifiable by all data providers. |

### Manifestation handle, e.g. from SDK

Handles describing a moving image manifestation or item (AVefi
category Manifestation or Item) are strictly owned by one data
provider in AVefi.

Sample record for a manifestation from SDK, e.g.
`21.11155/sample_manifestation`:

| index | type       | sample value (ePIC API v3)                                                          | remarks                                                                 |
|-------|------------|-------------------------------------------------------------------------------------|-------------------------------------------------------------------------|
| 1     | KIP        | http://typeapi.lab.pidconsortium.net/v1/types/schema/21.T11969/873d5c9f6ebbffecf1df | AVefi schema                                                            |
| 2     | has_record | {"category": "avefi:Manifestation", ...}                                            | Moving image manifestation record according to AVefi schema.            |
| 3     | URL        | https://www.av-efi.net/res/21.11155/sample_manifestation                            |                                                                         |
| 100   | HS_ADMIN   | {"adminId": "21.11155/USER1", "adminIdIndex": 300}                                  |                                                                         |
| 101   | HS_ADMIN   | {"adminId": "21.11155/SDK", "adminIdIndex": 200}                                    | Manifestation records are meant to be modifiable by all data providers. |

## Procedures

### Adding a new data provider

In preparation for submissions from a new data provider, two steps
need to be completed:
-   Add a PID according to the structure for data provider handles
    described above.
-   Add that PID to the VLIST in `200:21.11155/work_variant_editors`
    described above.
-   Configure a user with the new PID and corresponding keys in the
    ePIC API.
-   Communicate username and password to data provider as required.
