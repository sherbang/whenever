use core::ffi::{c_char, c_int, c_long, c_short, c_uint, c_ulonglong, c_void};
use core::{mem, ptr};
use pyo3_ffi::*;
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::ptr::null_mut;

#[repr(C)]
#[derive(Debug, Eq, PartialEq, Ord, PartialOrd, Hash)]
struct _Date {
    year: u16,
    month: u8,
    day: u8,
}

#[repr(C)]
pub struct PyDate {
    _ob_base: PyObject,
    date: _Date,
}

unsafe extern "C" fn new(
    subtype: *mut PyTypeObject,
    args: *mut PyObject,
    kwargs: *mut PyObject,
) -> *mut PyObject {
    let mut year: c_ulonglong = 0;
    let mut month: c_ulonglong = 0;
    let mut day: c_ulonglong = 0;

    if PyArg_ParseTupleAndKeywords(
        args,
        kwargs,
        "KKK:Date\0".as_ptr().cast::<c_char>(),
        vec![
            "year\0".as_ptr().cast::<c_char>() as *mut c_char,
            "month\0".as_ptr().cast::<c_char>() as *mut c_char,
            "day\0".as_ptr().cast::<c_char>() as *mut c_char,
            ptr::null_mut(),
        ]
        .as_mut_ptr(),
        &mut year,
        &mut month,
        &mut day,
    ) == 0
    {
        return ptr::null_mut();
    }

    let f: allocfunc = (*subtype).tp_alloc.unwrap_or(PyType_GenericAlloc);
    let slf = f(subtype, 0);
    if slf.is_null() {
        return ptr::null_mut();
    }

    match check_date(year, month, day) {
        Ok(date) => {
            ptr::addr_of_mut!((*slf.cast::<PyDate>()).date).write(date);
            slf
        }
        Err(DateError::InvalidYear) => {
            PyErr_SetString(
                PyExc_ValueError,
                "year is out of range\0".as_ptr().cast::<c_char>(),
            );
            ptr::null_mut()
        }
        Err(DateError::InvalidMonth) => {
            PyErr_SetString(
                PyExc_ValueError,
                "month must be in 1..12\0".as_ptr().cast::<c_char>(),
            );
            ptr::null_mut()
        }
        Err(DateError::InvalidDay) => {
            PyErr_SetString(
                PyExc_ValueError,
                "day is out of range\0".as_ptr().cast::<c_char>(),
            );
            ptr::null_mut()
        }
    }
}

unsafe extern "C" fn repr(slf: *mut PyObject) -> *mut PyObject {
    let slf = slf.cast::<PyDate>();
    let date = &(*slf).date;
    let string = format!("Date({:04}-{:02}-{:02})", date.year, date.month, date.day);
    PyUnicode_FromStringAndSize(string.as_ptr().cast::<c_char>(), string.len() as Py_ssize_t)
}

unsafe extern "C" fn hash(slf: *mut PyObject) -> Py_hash_t {
    let date = &(*slf.cast::<PyDate>()).date;
    let mut hasher = DefaultHasher::new();
    date.hash(&mut hasher);
    hasher.finish() as Py_hash_t
}

unsafe extern "C" fn richcmp(slf: *mut PyObject, other: *mut PyObject, op: c_int) -> *mut PyObject {
    if Py_TYPE(other) != Py_TYPE(slf) {
        let result = Py_NotImplemented();
        Py_INCREF(result);
        return result;
    }
    let slf = &(*slf.cast::<PyDate>()).date;
    let other = &(*other.cast::<PyDate>()).date;
    let cmp = match op {
        pyo3_ffi::Py_LT => slf < other,
        pyo3_ffi::Py_LE => slf <= other,
        pyo3_ffi::Py_EQ => slf == other,
        pyo3_ffi::Py_NE => slf != other,
        pyo3_ffi::Py_GT => slf > other,
        pyo3_ffi::Py_GE => slf >= other,
        _ => unreachable!(),
    };

    let result = if cmp { Py_True() } else { Py_False() };
    Py_INCREF(result);
    result
}

fn datetime_api() -> Option<&'static PyDateTime_CAPI> {
    if let Some(api) = unsafe { PyDateTimeAPI().as_ref() } {
        Some(api)
    } else {
        unsafe {
            PyDateTime_IMPORT();
            PyDateTimeAPI().as_ref()
        }
    }
}

unsafe extern "C" fn as_py_date(slf: *mut PyObject, _: *mut PyObject) -> *mut PyObject {
    let date = &(*slf.cast::<PyDate>()).date;
    match datetime_api() {
        Some(api) => (api.Date_FromDate)(
            date.year as c_int,
            date.month as c_int,
            date.day as c_int,
            api.DateType,
        ),
        None => ptr::null_mut(),
    }
}

static mut METHODS: &[PyMethodDef] = &[
    PyMethodDef {
        ml_name: "py_date\0".as_ptr().cast::<c_char>(),
        ml_meth: PyMethodDefPointer {
            PyCFunction: as_py_date,
        },
        ml_flags: METH_NOARGS,
        ml_doc: "Convert to a Python datetime.date\0"
            .as_ptr()
            .cast::<c_char>(),
    },
    PyMethodDef::zeroed(),
];

unsafe extern "C" fn get_year(slf: *mut PyObject, _: *mut c_void) -> *mut PyObject {
    PyLong_FromLong((*slf.cast::<PyDate>()).date.year as c_long)
}

unsafe extern "C" fn get_month(slf: *mut PyObject, _: *mut c_void) -> *mut PyObject {
    PyLong_FromLong((*slf.cast::<PyDate>()).date.month as c_long)
}

unsafe extern "C" fn get_day(slf: *mut PyObject, _: *mut c_void) -> *mut PyObject {
    PyLong_FromLong((*slf.cast::<PyDate>()).date.day as c_long)
}

static mut GETSETTERS: &[PyGetSetDef] = &[
    PyGetSetDef {
        name: "year\0".as_ptr().cast::<c_char>(),
        get: Some(get_year),
        set: None,
        doc: "The year component\0".as_ptr().cast::<c_char>(),
        closure: ptr::null_mut(),
    },
    PyGetSetDef {
        name: "month\0".as_ptr().cast::<c_char>(),
        get: Some(get_month),
        set: None,
        doc: "The month component\0".as_ptr().cast::<c_char>(),
        closure: ptr::null_mut(),
    },
    PyGetSetDef {
        name: "day\0".as_ptr().cast::<c_char>(),
        get: Some(get_day),
        set: None,
        doc: "The day component\0".as_ptr().cast::<c_char>(),
        closure: ptr::null_mut(),
    },
    PyGetSetDef {
        name: null_mut(),
        get: None,
        set: None,
        doc: null_mut(),
        closure: null_mut(),
    },
];

static mut SLOTS: &[PyType_Slot] = &[
    PyType_Slot {
        slot: Py_tp_new,
        pfunc: new as *mut c_void,
    },
    PyType_Slot {
        slot: Py_tp_doc,
        pfunc: "A calendar date type\0".as_ptr() as *mut c_void,
    },
    PyType_Slot {
        slot: Py_tp_repr,
        pfunc: repr as *mut c_void,
    },
    PyType_Slot {
        slot: Py_tp_richcompare,
        pfunc: richcmp as *mut c_void,
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
        slot: Py_tp_hash,
        pfunc: hash as *mut c_void,
    },
    PyType_Slot {
        slot: 0,
        pfunc: ptr::null_mut(),
    },
];

pub static mut SPEC: PyType_Spec = PyType_Spec {
    name: "whenever.Date\0".as_ptr().cast::<c_char>(),
    basicsize: mem::size_of::<PyDate>() as c_int,
    itemsize: 0,
    flags: Py_TPFLAGS_DEFAULT as c_uint,
    slots: unsafe { SLOTS as *const [PyType_Slot] as *mut PyType_Slot },
};

#[derive(Debug, Eq, PartialEq, Ord, PartialOrd)]
enum DateError {
    InvalidYear,
    InvalidMonth,
    InvalidDay,
}

const MAX_YEAR: u16 = 9999;
const MIN_YEAR: u16 = 1;
const DAYS_IN_MONTH: [u8; 13] = [
    0, // 1-indexed
    31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31,
];

fn is_leap(year: u16) -> bool {
    (year % 4 == 0 && year % 100 != 0) || year % 400 == 0
}

fn days_in_month(year: u16, month: u8) -> u8 {
    debug_assert!(month >= 1 && month <= 12);
    if month == 2 && is_leap(year) {
        29
    } else {
        DAYS_IN_MONTH[month as usize]
    }
}

fn check_date(year: u64, month: u64, day: u64) -> Result<_Date, DateError> {
    match u16::try_from(year) {
        Ok(y) => match u8::try_from(month) {
            Ok(m) => match u8::try_from(day) {
                Ok(d) => {
                    if y < MIN_YEAR || y > MAX_YEAR {
                        return Err(DateError::InvalidYear);
                    }
                    if m < 1 || m > 12 {
                        return Err(DateError::InvalidMonth);
                    }
                    if d < 1 || d > days_in_month(y, m) {
                        return Err(DateError::InvalidDay);
                    }
                    Ok(_Date {
                        year: y,
                        month: m,
                        day: d,
                    })
                }
                Err(_) => Err(DateError::InvalidDay),
            },
            Err(_) => Err(DateError::InvalidMonth),
        },
        Err(_) => Err(DateError::InvalidYear),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_check_date_valid() {
        assert_eq!(
            check_date(2021, 1, 1),
            Ok(_Date {
                year: 2021,
                month: 1,
                day: 1
            })
        );
        assert_eq!(
            check_date(2021, 12, 31),
            Ok(_Date {
                year: 2021,
                month: 12,
                day: 31
            })
        );
        assert_eq!(
            check_date(2021, 2, 28),
            Ok(_Date {
                year: 2021,
                month: 2,
                day: 28
            })
        );
        assert_eq!(
            check_date(2020, 2, 29),
            Ok(_Date {
                year: 2020,
                month: 2,
                day: 29
            })
        );
        assert_eq!(
            check_date(2021, 4, 30),
            Ok(_Date {
                year: 2021,
                month: 4,
                day: 30
            })
        );
        assert_eq!(
            check_date(2000, 2, 29),
            Ok(_Date {
                year: 2000,
                month: 2,
                day: 29
            })
        );
        assert_eq!(
            check_date(1900, 2, 28),
            Ok(_Date {
                year: 1900,
                month: 2,
                day: 28
            })
        );
    }

    #[test]
    fn test_check_date_invalid_year() {
        assert_eq!(check_date(0, 1, 1), Err(DateError::InvalidYear));
        assert_eq!(check_date(10_000, 1, 1), Err(DateError::InvalidYear));
    }

    #[test]
    fn test_check_date_invalid_month() {
        assert_eq!(check_date(2021, 0, 1), Err(DateError::InvalidMonth));
        assert_eq!(check_date(2021, 13, 1), Err(DateError::InvalidMonth));
    }

    #[test]
    fn test_check_date_invalid_day() {
        assert_eq!(check_date(2021, 1, 0), Err(DateError::InvalidDay));
        assert_eq!(check_date(2021, 1, 32), Err(DateError::InvalidDay));
        assert_eq!(check_date(2021, 4, 31), Err(DateError::InvalidDay));
        assert_eq!(check_date(2021, 2, 29), Err(DateError::InvalidDay));
        assert_eq!(check_date(2020, 2, 30), Err(DateError::InvalidDay));
        assert_eq!(check_date(2000, 2, 30), Err(DateError::InvalidDay));
        assert_eq!(check_date(1900, 2, 29), Err(DateError::InvalidDay));
    }
}
