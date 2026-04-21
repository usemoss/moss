[**@moss-dev/moss-web v1.0.0**](../README.md)

***

[@moss-dev/moss-web](../globals.md) / LoadIndexOptions

# Interface: LoadIndexOptions

## Properties

| Property | Type | Description |
| ------ | ------ | ------ |
| <a id="property-autorefresh"></a> `autoRefresh?` | `boolean` | Whether to enable auto-refresh polling for this index. When enabled, the index will periodically check for updates from the cloud. **Default** `false` |
| <a id="property-pollingintervalinseconds"></a> `pollingIntervalInSeconds?` | `number` | Polling interval in seconds. Only used when autoRefresh is true. **Default** `600 (10 minutes)` |
