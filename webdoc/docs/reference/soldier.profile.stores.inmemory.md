<a id="focal.profile.stores.inmemory"></a>

# focal.profile.stores.inmemory

In-memory implementation of ProfileStore.

<a id="focal.profile.stores.inmemory.InMemoryProfileStore"></a>

## InMemoryProfileStore Objects

```python
class InMemoryProfileStore(ProfileStore)
```

In-memory implementation of ProfileStore for testing and development.

<a id="focal.profile.stores.inmemory.InMemoryProfileStore.__init__"></a>

#### \_\_init\_\_

```python
def __init__() -> None
```

Initialize empty storage.

<a id="focal.profile.stores.inmemory.InMemoryProfileStore.get_by_customer_id"></a>

#### get\_by\_customer\_id

```python
async def get_by_customer_id(tenant_id: UUID,
                             customer_id: UUID) -> CustomerProfile | None
```

Get profile by customer ID.

<a id="focal.profile.stores.inmemory.InMemoryProfileStore.get_by_id"></a>

#### get\_by\_id

```python
async def get_by_id(tenant_id: UUID,
                    profile_id: UUID) -> CustomerProfile | None
```

Get profile by profile ID.

<a id="focal.profile.stores.inmemory.InMemoryProfileStore.get_by_channel_identity"></a>

#### get\_by\_channel\_identity

```python
async def get_by_channel_identity(
        tenant_id: UUID, channel: Channel,
        channel_user_id: str) -> CustomerProfile | None
```

Get profile by channel identity.

<a id="focal.profile.stores.inmemory.InMemoryProfileStore.get_or_create"></a>

#### get\_or\_create

```python
async def get_or_create(tenant_id: UUID, channel: Channel,
                        channel_user_id: str) -> CustomerProfile
```

Get existing profile or create new one for channel identity.

<a id="focal.profile.stores.inmemory.InMemoryProfileStore.save"></a>

#### save

```python
async def save(profile: CustomerProfile) -> UUID
```

Save a profile.

<a id="focal.profile.stores.inmemory.InMemoryProfileStore.update_field"></a>

#### update\_field

```python
async def update_field(tenant_id: UUID, profile_id: UUID,
                       field: ProfileField) -> bool
```

Update a profile field.

<a id="focal.profile.stores.inmemory.InMemoryProfileStore.add_asset"></a>

#### add\_asset

```python
async def add_asset(tenant_id: UUID, profile_id: UUID,
                    asset: ProfileAsset) -> bool
```

Add an asset to profile.

<a id="focal.profile.stores.inmemory.InMemoryProfileStore.link_channel"></a>

#### link\_channel

```python
async def link_channel(tenant_id: UUID, profile_id: UUID,
                       identity: ChannelIdentity) -> bool
```

Link a new channel identity to profile.

<a id="focal.profile.stores.inmemory.InMemoryProfileStore.merge_profiles"></a>

#### merge\_profiles

```python
async def merge_profiles(tenant_id: UUID, source_profile_id: UUID,
                         target_profile_id: UUID) -> bool
```

Merge source profile into target profile.

