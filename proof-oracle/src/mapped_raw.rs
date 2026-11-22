//! Linux shared raw files. No GPU or network access; no unsafe Send/Sync impls.
use anyhow::{ensure, Result};
use std::{ffi::c_void, fs::{File, OpenOptions}, os::{fd::AsRawFd, unix::fs::OpenOptionsExt}, path::Path, ptr::NonNull};

#[cfg(not(all(target_os="linux", target_pointer_width="64")))]
compile_error!("Mapped producer requires 64-bit Linux");
unsafe extern "C" {
 fn mmap(addr:*mut c_void, len:usize, prot:i32, flags:i32, fd:i32, offset:i64)->*mut c_void;
 fn munmap(addr:*mut c_void, len:usize)->i32;
}
pub struct MappedRaw { ptr:NonNull<u8>, len:usize, _file:File }
impl MappedRaw {
 pub fn create(path:&Path, len:usize)->Result<Self> {
  ensure!(len>0 && len<=1usize<<31,"invalid raw mapping size");
  // create_new rejects existing files and symlinks. Caller owns a private directory.
  let file=OpenOptions::new().read(true).write(true).create_new(true).mode(0o600).open(path)?;
  file.set_len(len as u64)?;
  // SAFETY: valid open RW descriptor; nonzero bounded size, offset zero.
  let address=unsafe{mmap(std::ptr::null_mut(),len,3,1,file.as_raw_fd(),0)};
  ensure!(address as usize!=usize::MAX,"mmap failed: {}",std::io::Error::last_os_error());
  let ptr=NonNull::new(address.cast::<u8>()).ok_or_else(||anyhow::anyhow!("null mmap address"))?;
  Ok(Self{ptr,len,_file:file})
 }
 pub fn bytes(&self)->&[u8] {
  // SAFETY: mapping lives as long as self; shared borrow excludes bytes_mut.
  unsafe{std::slice::from_raw_parts(self.ptr.as_ptr(),self.len)}
 }
 pub fn bytes_mut(&mut self)->&mut[u8] {
  // SAFETY: exclusive self borrow, valid writable mapping of exactly len bytes.
  unsafe{std::slice::from_raw_parts_mut(self.ptr.as_ptr(),self.len)}
 }
}
impl Drop for MappedRaw {
 fn drop(&mut self) {
  // SAFETY: this object owns this mapping; no slices can outlive self.
  unsafe{munmap(self.ptr.as_ptr().cast(),self.len);}
 }
}
#[cfg(test)] mod tests {
 use super::*;
 use std::{os::unix::fs::{PermissionsExt,symlink},sync::atomic::{AtomicUsize,Ordering}};
 static NEXT:AtomicUsize=AtomicUsize::new(0);
 #[test] fn mapped_files_persist_and_cannot_be_overwritten() {
  let dir=std::env::temp_dir().join(format!("pearl-map-{}-{}",std::process::id(),NEXT.fetch_add(1,Ordering::Relaxed)));
  std::fs::create_dir(&dir).unwrap();let path=dir.join("raw");
  {let mut m=MappedRaw::create(&path,8193).unwrap();assert!(m.bytes().iter().all(|&x|x==0));
   for(i,x)in m.bytes_mut().iter_mut().enumerate(){*x=(i%251)as u8;}
   assert!(MappedRaw::create(&path,1).is_err());}
  let got=std::fs::read(&path).unwrap();assert_eq!(got.len(),8193);
  assert!(got.iter().enumerate().all(|(i,&x)|x==(i%251)as u8));
  assert_eq!(std::fs::metadata(&path).unwrap().permissions().mode()&0o777,0o600);
  let link=dir.join("link");symlink(&path,&link).unwrap();assert!(MappedRaw::create(&link,1).is_err());
  assert!(MappedRaw::create(&dir.join("zero"),0).is_err());
  std::fs::remove_dir_all(dir).unwrap();
 }
}
