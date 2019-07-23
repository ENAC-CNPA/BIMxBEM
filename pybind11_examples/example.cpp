#include <pybind11/pybind11.h>

namespace py = pybind11;

int add(int i = 1, int j = 2) {
    return i + j;
};

struct Pet
{
    Pet(const std::string &name):name(name) { }
    void setName(const std::string &name_) { name = name_; }
    const std::string &getName() const { return name; }
    std::string name;
    std::string nick;
};


struct Dog : Pet 
{
    Dog(const std::string &name) : Pet(name) { }
    std::string bark() const { return "woof!"; }
};


PYBIND11_MODULE(example, m) {
    m.doc() = "pybind11 example plugin"; // optional module docstring

    m.def("add", &add, "A function which adds two numbers", py::arg("i")=1, py::arg("j")=2);

    m.attr("the_answer") = 42;
    py::object world = py::cast("World");
    m.attr("what") = world;

    py::class_<Pet>(m, "Pet")
        .def(py::init<const std::string &>())
        .def("setName", &Pet::setName)
        .def("getName", &Pet::getName)
        .def_readwrite("nick", &Pet::nick)
        .def("__repr__",[](const Pet &a) {
                return "<example.Pet named '" + a.name + "'>";
            }
        )
        ;

    py::class_<Dog, Pet>(m, "Dog")
        .def(py::init<const std::string &>())
        .def("bark", &Dog::bark)
        ;
};