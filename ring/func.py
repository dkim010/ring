"""Collection of cache decorators"""
import time
import functools
from ring import _func_util as futil

try:
    import asyncio
except ImportError:
    asyncio = False

__all__ = ('memcache', 'redis_py', 'redis', 'aiomcache', 'aioredis')


def wrapper_class(
        f, context, ckey,
        get_value, set_value, del_value, touch_value, miss_value,
        encode, decode):

    miss = object()

    class Ring(futil.WrapperBase):

        _ckey = ckey

        @functools.wraps(f)
        def __call__(self, *args, **kwargs):
            args = self.reargs(args, padding=False)
            return self._get_or_update(args, kwargs)

        def _key(self, args, kwargs):
            return self._ckey.build_key(args, kwargs)

        def _get(self, key):
            value = get_value(context, key)
            if value == miss_value:
                return miss
            else:
                return decode(value)

        def _update(self, key, args, kwargs):
            result = f(*args, **kwargs)
            value = encode(result)
            set_value(context, key, value)
            return result

        def _get_or_update(self, args, kwargs):
            key = self._key(args, kwargs)
            result = self._get(key)
            if result == miss:
                result = self._update(key, args, kwargs)
            return result

        def key(self, *args, **kwargs):
            args = self.reargs(args, padding=True)
            return self._key(args, kwargs)

        def execute(self, *args, **kwargs):
            args = self.reargs(args, padding=True)
            return f(*args, **kwargs)

        def get(self, *args, **kwargs):
            args = self.reargs(args, padding=True)
            key = self._key(args, kwargs)
            result = self._get(key)
            if result == miss:
                result = miss_value
            return result

        def update(self, *args, **kwargs):
            args = self.reargs(args, padding=True)
            key = self._key(args, kwargs)
            return self._update(key, args, kwargs)

        def get_or_update(self, *args, **kwargs):
            args = self.reargs(args, padding=True)
            return self._get_or_update(args, kwargs)

        def delete(self, *args, **kwargs):
            key = self.key(*args, **kwargs)
            del_value(context, key)

        def touch(self, *args, **kwargs):
            if not touch_value:
                f.touch  # to raise AttributeError
            key = self.key(*args, **kwargs)
            touch_value(context, key)

    return Ring


def dict(
        obj, key_prefix='', expire=None, coder=None, ignorable_keys=None,
        now=time.time):

    miss_value = None

    def get_value(obj, key):
        if now is None:
            _now = time.time()
        else:
            _now = now
        try:
            expired_time, value = obj[key]
        except KeyError:
            return miss_value
        if expired_time is not None and expired_time < _now:
            return miss_value
        return value

    def set_value(obj, key, value):
        if now is None:
            _now = time.time()
        else:
            _now = now
        if expire is None:
            expired_time = None
        else:
            expired_time = _now + expire
        obj[key] = expired_time, value

    def del_value(obj, key):
        try:
            del obj[key]
        except KeyError:
            pass

    def touch_value(obj, key):
        if now is None:
            _now = time.time()
        else:
            _now = now
        try:
            expired_time, value = obj[key]
        except KeyError:
            return
        if expire is None:
            expired_time = None
        else:
            expired_time = _now + expire
        obj[key] = expired_time, value

    return futil.factory(
        obj, key_prefix=key_prefix, wrapper_class=wrapper_class,
        get_value=get_value, set_value=set_value, del_value=del_value,
        touch_value=touch_value,
        miss_value=miss_value, coder=coder,
        ignorable_keys=ignorable_keys)


def memcache(client, key_prefix=None, time=0, coder=None, ignorable_keys=None):
    miss_value = None

    def get_value(client, key):
        value = client.get(key)
        return value

    def set_value(client, key, value):
        client.set(key, value, time)

    def del_value(client, key):
        client.delete(key)

    def touch_value(client, key):
        client.touch(key, time)

    return futil.factory(
        client, key_prefix=key_prefix, wrapper_class=wrapper_class,
        get_value=get_value, set_value=set_value, del_value=del_value,
        touch_value=touch_value,
        miss_value=miss_value, coder=coder,
        ignorable_keys=ignorable_keys)


def redis_py(
        client, key_prefix=None, expire=None, coder=None, ignorable_keys=None):
    miss_value = None

    def get_value(client, key):
        value = client.get(key)
        return value

    def set_value(client, key, value):
        client.set(key, value, expire)

    def del_value(client, key):
        client.delete(key)

    def touch_value(client, key):
        if expire is None:
            raise TypeError("'touch' is requested for persistant cache")
        client.expire(key, expire)

    return futil.factory(
        client, key_prefix=key_prefix, wrapper_class=wrapper_class,
        get_value=get_value, set_value=set_value, del_value=del_value,
        touch_value=touch_value,
        miss_value=miss_value, coder=coder,
        ignorable_keys=ignorable_keys)


redis = redis_py  # de facto standard of redis


if asyncio:
    from ring.func_asyncio import aiomcache, aioredis
