package mosscore

import "errors"

var ErrBindingsUnavailable = errors.New("mosscore: libmoss bindings are unavailable; build with -tags libmoss and configure the libmoss C SDK")
var ErrClientClosed = errors.New("mosscore: client is closed")
