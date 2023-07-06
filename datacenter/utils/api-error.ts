export enum ApiErrorType {
    UNAUTHORIZED = 'UNAUTHORIZED',
    USAGE_LIMIT = 'USAGE_LIMIT',
    NOT_FOUND = 'NOT_FOUND',
    INVALID_REQUEST = 'INVALID_REQUEST',
    WEBPAGE_IS_SITEMAP = 'WEBPAGE_IS_SITEMAP',
    EMPTY_DATASOURCE = 'EMPTY_DATASOURCE',
  }
  
  export class ApiError extends Error {
    constructor(message: ApiErrorType, public status?: number) {
      super(message);
  
      if (!status) {
        switch (message) {
          case ApiErrorType.UNAUTHORIZED:
            this.status = 403;
            break;
          case ApiErrorType.USAGE_LIMIT:
            this.status = 402;
            break;
          case ApiErrorType.NOT_FOUND:
            this.status = 404;
            break;
          case ApiErrorType.INVALID_REQUEST:
            this.status = 400;
            break;
          case ApiErrorType.EMPTY_DATASOURCE:
            this.status = 400;
            break;
          default:
            this.status = 500;
            break;
        }
      }
  
      Object.setPrototypeOf(this, ApiError.prototype);
    }
  }
  