<a id="focal.profile.store"></a>

# focal.profile.store

ProfileStore abstract interface.

<a id="focal.profile.store.ProfileStore"></a>

## ProfileStore Objects

```python
class ProfileStore(ABC)
```

Abstract interface for customer profile storage.

Manages customer profiles with support for channel
identity lookup and field updates.

<a id="focal.profile.store.ProfileStore.get_by_customer_id"></a>

#### get\_by\_customer\_id

```python
@abstractmethod
async def get_by_customer_id(tenant_id: UUID,
                             customer_id: UUID) -> CustomerProfile | None
```

Get profile by customer ID.

<a id="focal.profile.store.ProfileStore.get_by_id"></a>

#### get\_by\_id

```python
@abstractmethod
async def get_by_id(tenant_id: UUID,
                    profile_id: UUID) -> CustomerProfile | None
```

Get profile by profile ID.

<a id="focal.profile.store.ProfileStore.get_by_channel_identity"></a>

#### get\_by\_channel\_identity

```python
@abstractmethod
async def get_by_channel_identity(
        tenant_id: UUID, channel: Channel,
        channel_user_id: str) -> CustomerProfile | None
```

Get profile by channel identity.

<a id="focal.profile.store.ProfileStore.get_or_create"></a>

#### get\_or\_create

```python
@abstractmethod
async def get_or_create(tenant_id: UUID, channel: Channel,
                        channel_user_id: str) -> CustomerProfile
```

Get existing profile or create new one for channel identity.

<a id="focal.profile.store.ProfileStore.save"></a>

#### save

```python
@abstractmethod
async def save(profile: CustomerProfile) -> UUID
```

Save a profile.

<a id="focal.profile.store.ProfileStore.update_field"></a>

#### update\_field

```python
@abstractmethod
async def update_field(tenant_id: UUID, profile_id: UUID,
                       field: ProfileField) -> bool
```

Update a profile field.

<a id="focal.profile.store.ProfileStore.add_asset"></a>

#### add\_asset

```python
@abstractmethod
async def add_asset(tenant_id: UUID, profile_id: UUID,
                    asset: ProfileAsset) -> bool
```

Add an asset to profile.

<a id="focal.profile.store.ProfileStore.link_channel"></a>

#### link\_channel

```python
@abstractmethod
async def link_channel(tenant_id: UUID, profile_id: UUID,
                       identity: ChannelIdentity) -> bool
```

Link a new channel identity to profile.

<a id="focal.profile.store.ProfileStore.merge_profiles"></a>

#### merge\_profiles

```python
@abstractmethod
async def merge_profiles(tenant_id: UUID, source_profile_id: UUID,
                         target_profile_id: UUID) -> bool
```

Merge source profile into target profile.

