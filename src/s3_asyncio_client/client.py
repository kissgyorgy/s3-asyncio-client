from .buckets import _BucketOperations
from .multipart import _MultipartOperations
from .objects import _ObjectOperations


class S3Client(_BucketOperations, _ObjectOperations, _MultipartOperations):
    pass
