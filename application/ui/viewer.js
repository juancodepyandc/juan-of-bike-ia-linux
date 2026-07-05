import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { SMAAPass } from 'three/addons/postprocessing/SMAAPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

// Elements
const canvasContainer = document.getElementById('canvas-container');
const btnOrbit = document.getElementById('btn-orbit');
const btnFps = document.getElementById('btn-fps');
const instructionsFps = document.getElementById('instructions-fps');
const crosshair = document.getElementById('crosshair');
const btnLoadNatsu = document.getElementById('btn-load-natsu');
const fileInput = document.getElementById('file-input');
const loadingSpinner = document.getElementById('loading-spinner');

// State
let mode = 'orbit'; // 'orbit' or 'fps'
let currentModel = null;
let mixers = [];
let clock = new THREE.Clock();

// Three.js Setup
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0a0c);
scene.fog = new THREE.FogExp2(0x0a0a0c, 0.015);

const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 1.5, 4);

const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: "high-performance" });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.VSMShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
canvasContainer.appendChild(renderer.domElement);

// HDRI Environment for realistic reflections and PBR materials
const pmremGenerator = new THREE.PMREMGenerator(renderer);
pmremGenerator.compileEquirectangularShader();
scene.environment = pmremGenerator.fromScene(new RoomEnvironment(), 0.04).texture;

// Post-Processing Pipeline
const composer = new EffectComposer(renderer);
const renderPass = new RenderPass(scene, camera);
composer.addPass(renderPass);

// Subtle Bloom for glowing parts and highlights
const bloomPass = new UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 0.15, 0.4, 0.85);
composer.addPass(bloomPass);

// Output Pass for Tone Mapping
const outputPass = new OutputPass();
composer.addPass(outputPass);

// SMAA Anti-aliasing (Better than default MSAA for post-processing)
const smaaPass = new SMAAPass(window.innerWidth * renderer.getPixelRatio(), window.innerHeight * renderer.getPixelRatio());
composer.addPass(smaaPass);

// Lighting
const ambientLight = new THREE.AmbientLight(0xffffff, 0.2);
scene.add(ambientLight);

const dirLight = new THREE.DirectionalLight(0xfff5e6, 2.5);
dirLight.position.set(5, 10, 7);
dirLight.castShadow = true;
dirLight.shadow.mapSize.width = 4096;
dirLight.shadow.mapSize.height = 4096;
dirLight.shadow.camera.near = 0.5;
dirLight.shadow.camera.far = 25;
dirLight.shadow.camera.left = -10;
dirLight.shadow.camera.right = 10;
dirLight.shadow.camera.top = 10;
dirLight.shadow.camera.bottom = -10;
dirLight.shadow.bias = -0.0001;
scene.add(dirLight);

const fillLight = new THREE.DirectionalLight(0x88bbff, 0.8);
fillLight.position.set(-5, 3, -5);
scene.add(fillLight);

// Environment
const gridHelper = new THREE.GridHelper(50, 50, 0x333333, 0x111111);
scene.add(gridHelper);

// Floor for collisions
const floorGeometry = new THREE.PlaneGeometry(100, 100);
const floorMaterial = new THREE.MeshStandardMaterial({ 
    color: 0x111111,
    roughness: 0.8,
    metalness: 0.2
});
const floor = new THREE.Mesh(floorGeometry, floorMaterial);
floor.rotation.x = -Math.PI / 2;
floor.receiveShadow = true;
scene.add(floor);

// Controls
const orbitControls = new OrbitControls(camera, renderer.domElement);
orbitControls.enableDamping = true;
orbitControls.dampingFactor = 0.05;
orbitControls.target.set(0, 1, 0);

const fpsControls = new PointerLockControls(camera, document.body);

// FPS Physics State
const objects = [floor]; // Objects to collide with
let moveForward = false;
let moveBackward = false;
let moveLeft = false;
let moveRight = false;
let canJump = false;
let isRunning = false;

const velocity = new THREE.Vector3();
const direction = new THREE.Vector3();
const playerHeight = 1.6;
const raycaster = new THREE.Raycaster(new THREE.Vector3(), new THREE.Vector3(0, -1, 0), 0, playerHeight);
const horizontalRaycaster = new THREE.Raycaster(new THREE.Vector3(), new THREE.Vector3(), 0, 0.5);

// Mode Switching
function setMode(newMode) {
    mode = newMode;
    if (mode === 'orbit') {
        btnOrbit.classList.add('active');
        btnFps.classList.remove('active');
        instructionsFps.classList.add('hidden');
        crosshair.classList.add('hidden');
        
        fpsControls.unlock();
        orbitControls.enabled = true;
        
        // Reset camera for orbit
        camera.position.set(0, 1.5, 3);
        orbitControls.target.set(0, 1, 0);
    } else {
        btnFps.classList.add('active');
        btnOrbit.classList.remove('active');
        instructionsFps.classList.remove('hidden');
        
        orbitControls.enabled = false;
    }
}

btnOrbit.addEventListener('click', () => setMode('orbit'));
btnFps.addEventListener('click', () => setMode('fps'));

// FPS Locking
renderer.domElement.addEventListener('click', () => {
    if (mode === 'fps') {
        fpsControls.lock();
    }
});

fpsControls.addEventListener('lock', () => {
    instructionsFps.classList.add('hidden');
    crosshair.classList.remove('hidden');
});

fpsControls.addEventListener('unlock', () => {
    if (mode === 'fps') {
        instructionsFps.classList.remove('hidden');
        crosshair.classList.add('hidden');
    }
});

// FPS Keyboard Inputs (Layout Agnostic)
const onKeyDown = (event) => {
    const key = event.key.toLowerCase();
    if (key === 'w' || key === 'z' || event.code === 'ArrowUp') moveForward = true;
    if (key === 'a' || key === 'q' || event.code === 'ArrowLeft') moveLeft = true;
    if (key === 's' || event.code === 'ArrowDown') moveBackward = true;
    if (key === 'd' || event.code === 'ArrowRight') moveRight = true;
    if (event.code === 'Space') {
        if (canJump === true) velocity.y += 10;
        canJump = false;
    }
    if (event.code === 'ShiftLeft' || event.code === 'ShiftRight') isRunning = true;
};

const onKeyUp = (event) => {
    const key = event.key.toLowerCase();
    if (key === 'w' || key === 'z' || event.code === 'ArrowUp') moveForward = false;
    if (key === 'a' || key === 'q' || event.code === 'ArrowLeft') moveLeft = false;
    if (key === 's' || event.code === 'ArrowDown') moveBackward = false;
    if (key === 'd' || event.code === 'ArrowRight') moveRight = false;
    if (event.code === 'ShiftLeft' || event.code === 'ShiftRight') isRunning = false;
};

document.addEventListener('keydown', onKeyDown);
document.addEventListener('keyup', onKeyUp);

// Virtual Joysticks for Mobile (via Nipple.js if available)
let virtualMoveDir = new THREE.Vector2();
let virtualLookDir = new THREE.Vector2();

if (window.nipplejs) {
    const isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
    if (isTouch) {
        // Create joystick zones
        const leftZone = document.createElement('div');
        leftZone.style.cssText = 'position: absolute; bottom: 50px; left: 50px; width: 150px; height: 150px; z-index: 100;';
        const rightZone = document.createElement('div');
        rightZone.style.cssText = 'position: absolute; bottom: 50px; right: 50px; width: 150px; height: 150px; z-index: 100;';
        document.body.appendChild(leftZone);
        document.body.appendChild(rightZone);

        const moveJoystick = nipplejs.create({ zone: leftZone, mode: 'static', position: { left: '50%', top: '50%' }, color: 'white' });
        const lookJoystick = nipplejs.create({ zone: rightZone, mode: 'static', position: { left: '50%', top: '50%' }, color: 'white' });

        moveJoystick.on('move', (evt, data) => {
            virtualMoveDir.set(Math.cos(data.angle.radian) * data.distance, Math.sin(data.angle.radian) * data.distance);
        });
        moveJoystick.on('end', () => virtualMoveDir.set(0, 0));

        lookJoystick.on('move', (evt, data) => {
            virtualLookDir.set(Math.cos(data.angle.radian) * data.distance, Math.sin(data.angle.radian) * data.distance);
        });
        lookJoystick.on('end', () => virtualLookDir.set(0, 0));
        
        // Hide crosshair instructions on mobile
        instructionsFps.innerHTML = "<p>Utilisez les joysticks pour vous déplacer et regarder autour.</p>";
    }
}

// Model Loading
const loader = new GLTFLoader();

function loadModel(url) {
    loadingSpinner.classList.remove('hidden');
    
    if (currentModel) {
        scene.remove(currentModel);
        // Remove from collision objects
        const index = objects.indexOf(currentModel);
        if (index > -1) objects.splice(index, 1);
    }
    
    mixers = [];
    
    loader.load(
        url,
        (gltf) => {
            currentModel = gltf.scene;
            
            // Enable shadows
            currentModel.traverse((node) => {
                if (node.isMesh) {
                    node.castShadow = true;
                    node.receiveShadow = true;
                }
            });
            
            scene.add(currentModel);
            objects.push(currentModel); // Add to collision objects
            
            // Animations
            if (gltf.animations && gltf.animations.length > 0) {
                const mixer = new THREE.AnimationMixer(currentModel);
                gltf.animations.forEach((clip) => {
                    mixer.clipAction(clip).play();
                });
                mixers.push(mixer);
            }
            
            loadingSpinner.classList.add('hidden');
        },
        undefined,
        (error) => {
            console.error('Error loading model:', error);
            loadingSpinner.classList.add('hidden');
            alert('Erreur lors du chargement du modèle.');
        }
    );
}

// Load Natsu by default (from output folder)
btnLoadNatsu.addEventListener('click', () => {
    // Note: Assuming a local server is running at the root of the project to serve these files
    loadModel('../output/3d/pbr_natsu_v2_pack/pbr_natsu_v2_proc.glb');
});

// Load custom file
fileInput.addEventListener('change', (event) => {
    const file = event.target.files[0];
    if (file) {
        const url = URL.createObjectURL(file);
        loadModel(url);
    }
});

// Update Physics (Gravity & Collisions)
function updatePhysics(delta) {
    if (!fpsControls.isLocked) return;

    // Apply gravity
    velocity.y -= 25.0 * delta; 
    
    // Friction
    velocity.x -= velocity.x * 10.0 * delta;
    velocity.z -= velocity.z * 10.0 * delta;

    direction.z = Number(moveForward) - Number(moveBackward);
    direction.x = Number(moveRight) - Number(moveLeft);
    direction.normalize();

    const speed = isRunning ? 100.0 : 40.0;

    if (moveForward || moveBackward) velocity.z -= direction.z * speed * delta;
    if (moveLeft || moveRight) velocity.x -= direction.x * speed * delta;

    // Apply virtual joystick movement
    if (virtualMoveDir.lengthSq() > 0) {
        velocity.x += (virtualMoveDir.x / 50) * speed * delta;
        velocity.z -= (virtualMoveDir.y / 50) * speed * delta;
    }
    
    // Apply virtual joystick look
    if (virtualLookDir.lengthSq() > 0) {
        camera.rotation.y -= (virtualLookDir.x / 5000);
        camera.rotation.x += (virtualLookDir.y / 5000);
        // Clamp pitch
        camera.rotation.x = Math.max(-Math.PI/2, Math.min(Math.PI/2, camera.rotation.x));
    }

    // 1. Vertical Collision (Floor/Gravity)
    raycaster.ray.origin.copy(fpsControls.object.position);
    raycaster.ray.origin.y -= playerHeight;
    
    const intersections = raycaster.intersectObjects(objects, true);
    const onObject = intersections.length > 0;

    if (onObject === true) {
        velocity.y = Math.max(0, velocity.y);
        canJump = true;
    }

    // 2. Horizontal Collision (Walls)
    // We check in the direction of movement
    const moveDir = new THREE.Vector3(velocity.x, 0, velocity.z).normalize();
    if (moveDir.lengthSq() > 0) {
        horizontalRaycaster.ray.origin.copy(fpsControls.object.position);
        horizontalRaycaster.ray.origin.y -= playerHeight / 2; // Check from waist height
        horizontalRaycaster.ray.direction.copy(moveDir);
        
        // Transform moveDir relative to camera rotation
        const camEuler = new THREE.Euler(0, camera.rotation.y, 0, 'YXZ');
        moveDir.applyEuler(camEuler);
        horizontalRaycaster.ray.direction.copy(moveDir);

        const horizontalIntersects = horizontalRaycaster.intersectObjects(objects, true);
        
        if (horizontalIntersects.length > 0 && horizontalIntersects[0].distance < 0.5) {
            // Stop movement in that direction
            velocity.x = 0;
            velocity.z = 0;
        }
    }

    fpsControls.moveRight(-velocity.x * delta);
    fpsControls.moveForward(-velocity.z * delta);
    fpsControls.object.position.y += (velocity.y * delta);

    // Floor boundary check
    if (fpsControls.object.position.y < playerHeight) {
        velocity.y = 0;
        fpsControls.object.position.y = playerHeight;
        canJump = true;
    }
}

// Render Loop
function animate() {
    requestAnimationFrame(animate);
    
    const delta = clock.getDelta();
    
    // Update animations
    mixers.forEach((mixer) => mixer.update(delta));
    
    if (mode === 'orbit') {
        orbitControls.update();
    } else if (mode === 'fps') {
        updatePhysics(delta);
    }
    
    composer.render();
}

// Window resize handling
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    composer.setSize(window.innerWidth, window.innerHeight);
});

animate();
