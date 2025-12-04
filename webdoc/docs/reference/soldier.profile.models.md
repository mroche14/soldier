<a id="soldier.profile.models"></a>

# soldier.profile.models

Profile domain models.

Contains all Pydantic models for customer profiles.

<a id="soldier.profile.models.utc_now"></a>

#### utc\_now

```python
def utc_now() -> datetime
```

Return current UTC time.

<a id="soldier.profile.models.ChannelIdentity"></a>

## ChannelIdentity Objects

```python
class ChannelIdentity(BaseModel)
```

Customer identity on a channel.

<a id="soldier.profile.models.ProfileField"></a>

## ProfileField Objects

```python
class ProfileField(BaseModel)
```

Single customer fact.

Represents a single piece of customer data with full
provenance and verification tracking.

<a id="soldier.profile.models.ProfileAsset"></a>

## ProfileAsset Objects

```python
class ProfileAsset(BaseModel)
```

Document attached to profile.

<a id="soldier.profile.models.Consent"></a>

## Consent Objects

```python
class Consent(BaseModel)
```

Customer consent record.

<a id="soldier.profile.models.CustomerProfile"></a>

## CustomerProfile Objects

```python
class CustomerProfile(BaseModel)
```

Persistent customer data.

Contains all persistent information about a customer
spanning across sessions.

