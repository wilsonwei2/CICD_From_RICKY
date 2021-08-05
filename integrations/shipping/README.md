# Developer Guidelines

----
**Current issues and todos**

- None
----

## Prerequisites


## Serverless deploy and test

**Deploy stack**

    --stage [x|s|p]

```
serverless deploy -v --stage s
```

**Deploy function**
```
serverless deploy -v --function api --stage s
```

**Run locally**
```
serverless wsgi serve
```

## Configuration
### Config Editor

<table>
    <tr>
        <th>
            Path
        </th>
        <th>
            Value
        </th>
    </tr>
    <tr>
        <td>
            delivery_options => use_customizable_provider_rates
        </td>
        <td>
            True
        </td>
    </tr>
    <tr>
        <td>
            delivery_options => customization_adapter_config => base_url --> will be used for all carriers
        </td>
        <td>
            https://frankandoak.ps.{stage}.newstore.net/shipping/
        </td>
    </tr>
</table>


### Endpoints via Friendly URL
#### Implemented
```
https://frankandoak.ps.{stage}.newstore.net/shipping/provider_rates
https://frankandoak.ps.{stage}.newstore.net/shipping/carriers/shipping_offers
```


