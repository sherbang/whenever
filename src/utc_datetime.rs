use core::ffi::{c_char, c_int, c_long, c_void};
use core::{mem, ptr, ptr::null_mut as NULL};
use pyo3_ffi::*;

use crate::common::{c_str, identity, propagate_exc, py_str, raise, try_get_int};
use crate::naive_datetime::DateTime;
use crate::ModuleState;
use crate::{date, time};

// TODO: still need repr C?
#[repr(C)]
#[derive(Debug, Eq, PartialEq, Ord, PartialOrd, Copy, Clone)]
pub(crate) struct Instant {
    secs: u64,
    nanos: u32,
}

#[repr(C)]
pub(crate) struct PyUTCDateTime {
    _ob_base: PyObject,
    instant: Instant,
}

pub(crate) const SINGLETONS: [(&str, Instant); 0] = [];

impl Instant {
    pub(crate) fn to_datetime(&self) -> DateTime {
        let ord = (self.secs / 86400) as u32;
        let (year, month, day) = date::ord_to_ymd(ord);
        let hour = ((self.secs % 86400) / 3600) as u8;
        let minute = ((self.secs % 3600) / 60) as u8;
        let second = (self.secs % 60) as u8;
        DateTime {
            date: date::Date { year, month, day },
            time: time::Time {
                hour,
                minute,
                second,
                nanos: self.nanos,
            },
        }
    }

    pub(crate) fn from_datetime(dt: &DateTime) -> Self {
        let ord = date::ymd_to_ord(dt.date.year, dt.date.month, dt.date.day);
        let secs = ord as u64 * 86400
            + dt.time.hour as u64 * 3600
            + dt.time.minute as u64 * 60
            + dt.time.second as u64;
        Instant {
            secs,
            nanos: dt.time.nanos,
        }
    }
}

unsafe extern "C" fn __new__(
    subtype: *mut PyTypeObject,
    args: *mut PyObject,
    kwargs: *mut PyObject,
) -> *mut PyObject {
    let mut year: c_long = 0;
    let mut month: c_long = 0;
    let mut day: c_long = 0;
    let mut hour: c_long = 0;
    let mut minute: c_long = 0;
    let mut second: c_long = 0;
    let mut nanos: c_long = 0;

    // FUTURE: parse them manually, which is more efficient
    if PyArg_ParseTupleAndKeywords(
        args,
        kwargs,
        c_str!("lll|llll:UTCDateTime"),
        vec![
            c_str!("year") as *mut c_char,
            c_str!("month") as *mut c_char,
            c_str!("day") as *mut c_char,
            c_str!("hour") as *mut c_char,
            c_str!("minute") as *mut c_char,
            c_str!("second") as *mut c_char,
            c_str!("nanosecond") as *mut c_char,
            NULL(),
        ]
        .as_mut_ptr(),
        &mut year,
        &mut month,
        &mut day,
        &mut hour,
        &mut minute,
        &mut second,
        &mut nanos,
    ) == 0
    {
        return NULL();
    }

    new_unchecked(
        subtype,
        Instant::from_datetime(&DateTime {
            date: match date::in_range(year, month, day) {
                Ok(date) => date,
                Err(err) => {
                    err.set_pyerr();
                    return NULL();
                }
            },
            time: match time::in_range(hour, minute, second, nanos) {
                Some(time) => time,
                None => {
                    raise!(PyExc_ValueError, "Invalid time");
                }
            },
        }),
    )
    .cast()
}

pub(crate) unsafe fn new_unchecked(type_: *mut PyTypeObject, i: Instant) -> *mut PyUTCDateTime {
    let f: allocfunc = (*type_).tp_alloc.expect("tp_alloc is not set");
    let slf = propagate_exc!(f(type_, 0).cast::<PyUTCDateTime>());
    ptr::addr_of_mut!((*slf).instant).write(i);
    slf
}

unsafe extern "C" fn dealloc(slf: *mut PyObject) {
    let tp_free = PyType_GetSlot(Py_TYPE(slf), Py_tp_free);
    debug_assert_ne!(tp_free, NULL());
    let f: freefunc = std::mem::transmute(tp_free);
    f(slf.cast());
}

unsafe extern "C" fn __repr__(_: *mut PyObject) -> *mut PyObject {
    py_str("UTCDateTime()")
}

unsafe extern "C" fn __str__(slf: *mut PyObject) -> *mut PyObject {
    py_str("TODO")
}

unsafe extern "C" fn canonical_format(slf: *mut PyObject, _: *mut PyObject) -> *mut PyObject {
    py_str("canonical format")
}

unsafe extern "C" fn __richcmp__(
    slf: *mut PyObject,
    other: *mut PyObject,
    op: c_int,
) -> *mut PyObject {
    let result = if Py_TYPE(other) == Py_TYPE(slf) {
        let a = (*slf.cast::<PyUTCDateTime>()).instant;
        let b = (*other.cast::<PyUTCDateTime>()).instant;
        let cmp = match op {
            pyo3_ffi::Py_LT => a < b,
            pyo3_ffi::Py_LE => a <= b,
            pyo3_ffi::Py_EQ => a == b,
            pyo3_ffi::Py_NE => a != b,
            pyo3_ffi::Py_GT => a > b,
            pyo3_ffi::Py_GE => a >= b,
            _ => unreachable!(),
        };
        if cmp {
            Py_True()
        } else {
            Py_False()
        }
    } else {
        Py_NotImplemented()
    };
    Py_INCREF(result);
    result
}

unsafe extern "C" fn __hash__(slf: *mut PyObject) -> Py_hash_t {
    let instant = (*slf.cast::<PyUTCDateTime>()).instant;
    #[cfg(target_pointer_width = "64")]
    {
        (instant.secs ^ instant.nanos as u64) as Py_hash_t
    }
    #[cfg(target_pointer_width = "32")]
    {
        // TODO
        todo!()
    }
}

static mut SLOTS: &[PyType_Slot] = &[
    PyType_Slot {
        slot: Py_tp_new,
        pfunc: __new__ as *mut c_void,
    },
    PyType_Slot {
        slot: Py_tp_doc,
        pfunc: "A calendar date type\0".as_ptr() as *mut c_void,
    },
    PyType_Slot {
        slot: Py_tp_repr,
        pfunc: __repr__ as *mut c_void,
    },
    PyType_Slot {
        slot: Py_tp_str,
        pfunc: __str__ as *mut c_void,
    },
    PyType_Slot {
        slot: Py_tp_richcompare,
        pfunc: __richcmp__ as *mut c_void,
    },
    PyType_Slot {
        slot: Py_tp_hash,
        pfunc: __hash__ as *mut c_void,
    },
    PyType_Slot {
        slot: Py_tp_methods,
        pfunc: unsafe { METHODS.as_ptr() as *mut c_void },
    },
    PyType_Slot {
        slot: Py_tp_getset,
        pfunc: unsafe { GETSETTERS.as_ptr() as *mut c_void },
    },
    PyType_Slot {
        slot: Py_tp_dealloc,
        pfunc: dealloc as *mut c_void,
    },
    PyType_Slot {
        slot: 0,
        pfunc: NULL(),
    },
];

unsafe extern "C" fn __reduce__(slf: *mut PyObject, _: *mut PyObject) -> *mut PyObject {
    let ins = (*slf.cast::<PyUTCDateTime>()).instant;
    PyTuple_Pack(
        2,
        (*ModuleState::from(Py_TYPE(slf))).unpickle_utc_datetime,
        propagate_exc!(PyTuple_Pack(
            2,
            PyLong_FromLongLong(ins.secs as _),
            PyLong_FromLong(ins.nanos as _),
        )),
    )
}

pub(crate) unsafe extern "C" fn unpickle(
    module: *mut PyObject,
    args: *mut *mut PyObject,
    nargs: Py_ssize_t,
) -> *mut PyObject {
    if PyVectorcall_NARGS(nargs as usize) != 2 {
        raise!(PyExc_TypeError, "Invalid pickle data");
    }
    new_unchecked(
        (*PyModule_GetState(module).cast::<ModuleState>()).naive_datetime_type,
        Instant {
            secs: try_get_int!(*args.offset(0)) as u64,
            nanos: try_get_int!(*args.offset(1)) as u32,
        },
    )
    .cast()
}

static mut METHODS: &[PyMethodDef] = &[
    PyMethodDef {
        ml_name: c_str!("__copy__"),
        ml_meth: PyMethodDefPointer {
            PyCFunction: identity,
        },
        ml_flags: METH_NOARGS,
        ml_doc: NULL(),
    },
    PyMethodDef {
        ml_name: c_str!("__deepcopy__"),
        ml_meth: PyMethodDefPointer {
            PyCFunction: identity,
        },
        ml_flags: METH_O,
        ml_doc: NULL(),
    },
    PyMethodDef {
        ml_name: c_str!("__reduce__"),
        ml_meth: PyMethodDefPointer {
            PyCFunction: __reduce__,
        },
        ml_flags: METH_NOARGS,
        ml_doc: NULL(),
    },
    PyMethodDef::zeroed(),
];

unsafe extern "C" fn get_year(slf: *mut PyObject, _: *mut c_void) -> *mut PyObject {
    let (year, _, _) = date::ord_to_ymd(((*slf.cast::<PyUTCDateTime>()).instant.secs / 86400) as _);
    PyLong_FromLong(year as _)
}

unsafe extern "C" fn get_month(slf: *mut PyObject, _: *mut c_void) -> *mut PyObject {
    let (_, month, _) =
        date::ord_to_ymd(((*slf.cast::<PyUTCDateTime>()).instant.secs / 86400) as _);
    PyLong_FromLong(month as _)
}

unsafe extern "C" fn get_day(slf: *mut PyObject, _: *mut c_void) -> *mut PyObject {
    let (_, _, day) = date::ord_to_ymd(((*slf.cast::<PyUTCDateTime>()).instant.secs / 86400) as _);
    PyLong_FromLong(day as _)
}

unsafe extern "C" fn get_hour(slf: *mut PyObject, _: *mut c_void) -> *mut PyObject {
    PyLong_FromUnsignedLong(((*slf.cast::<PyUTCDateTime>()).instant.secs % 86400 / 3600) as _)
}

unsafe extern "C" fn get_minute(slf: *mut PyObject, _: *mut c_void) -> *mut PyObject {
    PyLong_FromUnsignedLong(((*slf.cast::<PyUTCDateTime>()).instant.secs % 3600 / 60) as _)
}

unsafe extern "C" fn get_secs(slf: *mut PyObject, _: *mut c_void) -> *mut PyObject {
    PyLong_FromUnsignedLong(((*slf.cast::<PyUTCDateTime>()).instant.secs % 60) as _)
}

unsafe extern "C" fn get_nanos(slf: *mut PyObject, _: *mut c_void) -> *mut PyObject {
    PyLong_FromUnsignedLong((*slf.cast::<PyUTCDateTime>()).instant.nanos as _)
}

static mut GETSETTERS: &[PyGetSetDef] = &[
    PyGetSetDef {
        name: c_str!("year"),
        get: Some(get_year),
        set: None,
        doc: c_str!("The year component"),
        closure: NULL(),
    },
    PyGetSetDef {
        name: c_str!("month"),
        get: Some(get_month),
        set: None,
        doc: c_str!("The month component"),
        closure: NULL(),
    },
    PyGetSetDef {
        name: c_str!("day"),
        get: Some(get_day),
        set: None,
        doc: c_str!("The day component"),
        closure: NULL(),
    },
    PyGetSetDef {
        name: c_str!("hour"),
        get: Some(get_hour),
        set: None,
        doc: c_str!("The hour component"),
        closure: NULL(),
    },
    PyGetSetDef {
        name: c_str!("minute"),
        get: Some(get_minute),
        set: None,
        doc: c_str!("The minute component"),
        closure: NULL(),
    },
    PyGetSetDef {
        name: c_str!("second"),
        get: Some(get_secs),
        set: None,
        doc: c_str!("The second component"),
        closure: NULL(),
    },
    PyGetSetDef {
        name: c_str!("nanosecond"),
        get: Some(get_nanos),
        set: None,
        doc: c_str!("The nanosecond component"),
        closure: NULL(),
    },
    PyGetSetDef {
        name: NULL(),
        get: None,
        set: None,
        doc: NULL(),
        closure: NULL(),
    },
];

pub(crate) static mut SPEC: PyType_Spec = PyType_Spec {
    name: c_str!("whenever.UTCDateTime"),
    basicsize: mem::size_of::<PyUTCDateTime>() as _,
    itemsize: 0,
    flags: Py_TPFLAGS_DEFAULT as _,
    slots: unsafe { SLOTS as *const [_] as *mut _ },
};
