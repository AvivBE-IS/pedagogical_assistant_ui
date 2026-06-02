const DB_NAME = "pedagogical_assistant";
const DB_VERSION = 1;
const STORE_LESSON = "lessonMaterials";
const STORE_COURSE = "courseMaterials";

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE_LESSON)) {
        db.createObjectStore(STORE_LESSON);
      }
      if (!db.objectStoreNames.contains(STORE_COURSE)) {
        db.createObjectStore(STORE_COURSE);
      }
    };
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror = (e) => reject(e.target.error);
  });
}

export async function dbSave(storeName, key, value) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, "readwrite");
    tx.objectStore(storeName).put(value, key);
    tx.oncomplete = () => resolve();
    tx.onerror = (e) => reject(e.target.error);
  });
}

export async function dbLoadAll(storeName) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, "readonly");
    const result = {};
    tx.objectStore(storeName).openCursor().onsuccess = (e) => {
      const cursor = e.target.result;
      if (cursor) {
        result[cursor.key] = cursor.value;
        cursor.continue();
      } else {
        resolve(result);
      }
    };
    tx.onerror = (e) => reject(e.target.error);
  });
}

export const STORE_LESSON_MATERIALS = STORE_LESSON;
export const STORE_COURSE_MATERIALS = STORE_COURSE;
